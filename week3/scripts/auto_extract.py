#!/usr/bin/env python3
"""
自动提取: 从 PyMuPDF 解析的招股书 MD 中自动提取股本变化数据

输入: review/*.md (招股书PDF解析后的Markdown)
输出: subscription_flow + equity_snapshot 行级记录

方法: 正则 + 表格解析 + 关键词定位
- 找到"发行人基本情况"章节
- 解析 HTML 股权结构表格
- 提取"增资"/"股权转让"/"整体变更"等事件
- 提取认购方、金额、价格、持股比例

这是"机器可运行"的自动提取流水线，不是人工整理报告。
"""
import re
import json
from pathlib import Path
from collections import defaultdict

REVIEW_DIR = Path(__file__).resolve().parent.parent / "review"

# 8家公司 → MD文件 映射
COMPANY_MD_MAP = {
    ("芜湖三联锻造股份有限公司", "001282", "三联锻造"): ["三联锻造_招股书_PyMuPDF.md"],
    ("上海友升铝业股份有限公司", "603418", "友升股份"): ["友升股份2.md"],
    ("黄山谷捷股份有限公司", "301581", "黄山谷捷"): ["黄山谷捷_招股书_PyMuPDF.md"],
    ("云汉芯城（上海）互联网科技股份有限公司", "301563", "云汉芯城"): ["云汉芯城_招股书_PyMuPDF.md"],
    ("苏州赛分科技股份有限公司", "688758", "赛分科技"): ["688758_赛分科技_招股书_正式稿_20250106.md"],
    ("影石创新科技股份有限公司", "688775", "影石创新"): ["688775_影石创新_招股书_正式稿_20250606.md"],
    ("常州三协电机股份有限公司", "920100", "三协电机"): ["三协电机_招股书_正式稿_20250711.md"],
    ("中科星图测控技术股份有限公司", "920116", "星图测控"): ["星图测控_招股书_正式稿_20241220.md"],
}


def read_company_md(company_key):
    """读取一家公司的所有MD文件，合并文本"""
    for (full_name, code, key), md_files in COMPANY_MD_MAP.items():
        if key == company_key:
            text = ""
            for mdf in md_files:
                p = REVIEW_DIR / mdf
                if p.exists():
                    text += p.read_text(encoding="utf-8", errors="ignore") + "\n\n"
            return text, full_name, code
    return "", "", ""


def parse_html_table(text, start_pos):
    """解析HTML表格，返回 [{col1: val1, col2: val2}, ...]"""
    table_end = text.find("</table>", start_pos)
    if table_end < 0:
        return []
    table_html = text[start_pos:table_end + 8]

    # 提取表头
    headers = re.findall(r'<td[^>]*>(.*?)</td>', table_html, re.DOTALL)
    # 简化: 找所有行
    rows = re.findall(r'<tr>(.*?)</tr>', table_html, re.DOTALL)

    result = []
    for row in rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
        if cells and any(c for c in cells if c):
            result.append(cells)
    return result


def extract_shareholder_table(text, headers_contain):
    """找包含特定表头的股权结构表"""
    for m in re.finditer(r'<table>', text):
        pos = m.start()
        table_end = text.find("</table>", pos)
        if table_end < 0:
            continue
        table_html = text[pos:table_end + 8]
        # 检查表头是否包含目标关键词
        first_row = re.search(r'<tr>(.*?)</tr>', table_html, re.DOTALL)
        if first_row:
            header_text = first_row.group(1).lower()
            if all(h in header_text for h in headers_contain):
                return parse_html_table(text, pos)
    return []


def find_section(text, keywords, max_results=3):
    """在文本中定位包含关键词的章节"""
    positions = []
    for kw in keywords:
        for m in re.finditer(kw, text):
            pos = m.start()
            # 向前找最近的页码标记
            prev_newline = text.rfind("\n", max(0, pos - 2000), pos)
            start = max(0, prev_newline)
            # 向后取3000字符
            end = min(len(text), pos + 3000)
            # 找到下一个 ## 第N页 边界
            next_page = text.find("## 第", pos + 100)
            if next_page > 0 and next_page < end:
                end = next_page
            snippet = text[start:end]
            positions.append((pos, snippet[:2000]))
            if len(positions) >= max_results:
                break
        if positions:
            break
    return positions


def extract_events_from_text(text, snippet):
    """从文本片段中提取融资事件"""
    events = []

    # 1. 找"设立"事件
    setup_matches = re.finditer(
        r'(?:有限公司|股份公司|股份有限公司)\s*设立.*?(?:注册资本|出资).*?(\d{4})\s*年\s*(\d{1,2})\s*月',
        snippet
    )
    for m in setup_matches:
        date_str = f"{m.group(1)}-{int(m.group(2)):02d}"
        ctx_start = max(0, m.start() - 200)
        ctx_end = min(len(snippet), m.end() + 500)
        evidence = snippet[ctx_start:ctx_end].strip()[:500]
        events.append({
            "event_type": "设立",
            "event_date": date_str,
            "evidence_text": evidence,
            "notes": "自动提取（设立事件）",
        })
        break  # 只取第一个设立事件

    # 2. 找"整体变更"事件
    change_matches = re.finditer(
        r'整体变更.*?(\d{4})\s*年\s*(\d{1,2})\s*月.*?(?:净资产|折股|股本)',
        snippet
    )
    for m in change_matches:
        date_str = f"{m.group(1)}-{int(m.group(2)):02d}"
        ctx_start = max(0, m.start() - 300)
        ctx_end = min(len(snippet), m.end() + 500)
        evidence = snippet[ctx_start:ctx_end].strip()[:500]
        events.append({
            "event_type": "整体变更",
            "event_date": date_str,
            "evidence_text": evidence,
            "notes": "自动提取（股改事件）",
        })
        break

    # 3. 找"增资"事件 (按年份+增资关键词)
    for m in re.finditer(
        r'(\d{4})\s*年\s*(\d{1,2})\s*月[^。]{0,100}?(?:增资|增加注册资本|新增注册资本)',
        snippet
    ):
        date_str = f"{m.group(1)}-{int(m.group(2)):02d}"
        ctx_start = max(0, m.start() - 100)
        ctx_end = min(len(snippet), m.end() + 300)
        evidence = snippet[ctx_start:ctx_end].strip()[:500]
        events.append({
            "event_type": "增资",
            "event_date": date_str,
            "evidence_text": evidence,
            "notes": "自动提取（增资事件）",
        })

    return events


def auto_extract_company(company_key):
    """对一家公司执行全自动提取"""
    text, full_name, code = read_company_md(company_key)
    if not text:
        print(f"  ⚠ {company_key}: 无MD文件")
        return [], []

    # 1. 定位"发行人基本情况"章节
    section_snippets = find_section(text, [
        "发行人基本情况",
        "股本演变", "历次增资", "股权转让",
        "设立情况", "股东变化", "报告期内股本"
    ], max_results=5)

    # 2. 合并所有找到的片段
    all_snippets = "\n".join(s[1] for s in section_snippets)

    # 3. 提取事件
    events = extract_events_from_text(text, all_snippets or text[:100000])

    # 4. 找股权结构表格
    shareholder_tables = []
    for h in [["序号", "股东"], ["股东名称", "持股"], ["出资额", "出资比例"]]:
        tbl = extract_shareholder_table(text, h)
        if tbl and len(tbl) > 1:
            shareholder_tables.append(tbl)
            break

    # 5. 构建 subscription_flow 和 equity_snapshot
    sub_flows = []
    eq_snaps = []

    for i, ev in enumerate(events):
        date_str = ev["event_date"]
        ev_type = ev["event_type"]
        evidence = ev["evidence_text"]

        # 从 evidence 中提取认购方信息
        # 找"XX认购XX万股"模式
        investors_found = re.findall(
            r'([一-鿿\w（）()]{2,30}(?:有限(?:责任)?公司|合伙|企业|基金|创投|投资|集团))(?:[^。]{0,80}?(?:认购|认缴|出资)[^。]{0,30}?)?(\d+[\d,.]*\s*万)?',
            evidence
        )

        inv_names = list(set(n for n, _ in investors_found if len(n) >= 4))[:5]

        # 提取金额
        amounts = re.findall(r'(\d+[\d,.]*)\s*万\s*元', evidence)

        # 找价格
        prices = re.findall(r'(\d+\.?\d*)\s*元\s*/\s*(?:股|注册资本)', evidence)
        price = float(prices[0]) if prices else None

        for j, inv_name in enumerate(inv_names):
            amt = float(amounts[j].replace(",", "")) if j < len(amounts) else None
            sub_flows.append({
                "record_type": "subscription_flow",
                "company_name": full_name,
                "stock_code": code,
                "source_page": f"auto_extract:{company_key}",
                "subscription_date": date_str,
                "subscriber_name": inv_name,
                "shares_subscribed": None,
                "amount_subscribed": amt,
                "price_per_share": price,
                "event_context": ev_type,
                "evidence_text": evidence[:500],
                "notes": f"自动提取 ({ev_type})",
            })

        # 如果没找到投资人，至少建一条占位记录
        if not inv_names:
            sub_flows.append({
                "record_type": "subscription_flow",
                "company_name": full_name,
                "stock_code": code,
                "source_page": f"auto_extract:{company_key}",
                "subscription_date": date_str,
                "subscriber_name": "待人工确认",
                "shares_subscribed": None,
                "amount_subscribed": float(amounts[0].replace(",", "")) if amounts else None,
                "price_per_share": price,
                "event_context": ev_type,
                "evidence_text": evidence[:500],
                "notes": f"自动提取 ({ev_type}) - 投资人名待确认",
            })

    # 从股权结构表中提取 snapshot
    if shareholder_tables:
        tbl = shareholder_tables[0]
        # 推断 snapshot_date 为最近的 event date
        snap_date = events[-1]["event_date"] if events else "2020-01"
        snap_type = "自动提取"

        # 找 column indices
        header = tbl[0] if tbl else []
        name_idx = next((i for i, h in enumerate(header) if '股东' in h or '名称' in h), 0)
        shares_idx = next((i for i, h in enumerate(header) if '持股' in h or '股份' in h or '股' in h), 1)
        ratio_idx = next((i for i, h in enumerate(header) if '比例' in h or '%' in h), 2)
        capital_idx = next((i for i, h in enumerate(header) if '出资额' in h or '注册资本' in h), -1)

        total_shares = None
        for row in tbl[1:]:
            if len(row) <= name_idx:
                continue
            if '合计' in row[0] or '总计' in row[0]:
                # 提取总股本
                try:
                    total_shares = float(re.sub(r'[^\d.]', '', str(row[shares_idx] if shares_idx < len(row) else '')) or 0) or None
                except:
                    pass
                continue

            name = row[name_idx] if name_idx < len(row) else ""
            if not name or len(name) < 2:
                continue

            shares = None
            if shares_idx < len(row):
                try:
                    shares = float(re.sub(r'[^\d.]', '', str(row[shares_idx]))) or None
                except:
                    pass

            ratio = None
            if ratio_idx < len(row):
                ratio_str = str(row[ratio_idx])
                ratio_match = re.search(r'(\d+\.?\d*)\s*%', ratio_str)
                if ratio_match:
                    ratio = ratio_match.group(1) + "%"

            capital = None
            if capital_idx >= 0 and capital_idx < len(row):
                try:
                    capital = float(re.sub(r'[^\d.]', '', str(row[capital_idx]))) or None
                except:
                    pass

            eq_snaps.append({
                "record_type": "equity_snapshot",
                "company_name": full_name,
                "stock_code": code,
                "source_page": f"auto_extract:{company_key}",
                "snapshot_date": snap_date,
                "snapshot_type": snap_type,
                "total_shares": total_shares,
                "total_capital": None,
                "shareholder_name": name,
                "shares_held": shares,
                "capital_contribution": capital,
                "shareholding_ratio": ratio,
                "snapshot_order": 0,
                "evidence_text": f"自动从股权结构表提取: 股东{name} 持股{shares}万股 占比{ratio}。原始表格共{len(tbl)}行，需人工核对PDF原文。",
                "notes": "自动提取 - 待人工复核以补充PDF原文证据",
            })

    return sub_flows, eq_snaps


def auto_extract_all():
    """对所有8家公司执行自动提取"""
    results = {}
    for (full_name, code, key), _ in COMPANY_MD_MAP.items():
        print(f"  {key} ({code})...")
        flows, snaps = auto_extract_company(key)
        results[key] = {
            "code": code,
            "full_name": full_name,
            "subscription_flows": len(flows),
            "equity_snapshots": len(snaps),
            "flows": flows,
            "snaps": snaps,
        }
        print(f"    -> {len(flows)} flows + {len(snaps)} snapshots")
    return results


if __name__ == "__main__":
    print("=" * 60)
    print("自动提取: 8家公司股本变化")
    print("=" * 60)
    results = auto_extract_all()
    total_f = sum(r["subscription_flows"] for r in results.values())
    total_s = sum(r["equity_snapshots"] for r in results.values())
    print(f"\n总计: {total_f} 认缴流量 + {total_s} 股权存量")
