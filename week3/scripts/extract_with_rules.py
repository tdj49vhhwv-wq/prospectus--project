#!/usr/bin/env python3
"""
自动提取 (规则/Rules): 从PDF解析MD中自动提取股本变化数据

方法: 正则 + 表格解析 + 关键词定位
输入: review/*.md (PyMuPDF解析的招股书) — ⚠人工环节(PDF下载)
输出: week3/outputs/auto_jsonl/auto_subscription_flow.jsonl
      week3/outputs/auto_jsonl/auto_equity_snapshot.jsonl

⚠ 人工环节: 此脚本依赖上游PDF→MD转换。
   - PDF下载: 人工从巨潮资讯网(cninfo.com.cn)下载招股书PDF
   - PDF解析: python3 parse_pdf.py (PyMuPDF,输出到review/*.md)
"""
import re, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline_config import *

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
    for (full_name, code, key), md_files in COMPANY_MD_MAP.items():
        if key == company_key:
            text = ""
            for mdf in md_files:
                p = REVIEW_DIR / mdf
                if p.exists():
                    text += p.read_text(encoding="utf-8", errors="ignore") + "\n\n"
            return text, full_name, code
    return "", "", ""


def normalize_date(date_str):
    """将中文日期转为 YYYY-MM-DD 格式: 2019年12月17日 → 2019-12-17"""
    m = re.match(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', date_str)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.match(r'(\d{4})\s*年\s*(\d{1,2})\s*月', date_str)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    return date_str.replace(' ', '')


def extract_flows(text, full_name, code):
    """正则提取认缴流量"""
    rows = []
    patterns = [
        # 增资: 关键词"增资""新增注册资本""增加注册资本""认购""发行股份"
        (r'(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日).*?(?:增资|新增注册资本|增加注册资本|认购.*新增|定向发行)', '增资'),
        # 股权转让: 关键词"转让给""转让予""将其.*转让"
        (r'(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日).*?(?:转让(?:给|予)|将其所持.*?转让)', '股权转让'),
        # 设立: 关键词"设立""成立"+"注册资本""出资"
        (r'(\d{4}\s*年\s*\d{1,2}\s*月).*?(?:设立|成立).{0,50}?(?:注册资本|出资)', '设立'),
        # 整体变更(股改): "整体变更设立股份有限公司"
        (r'(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日).*?整体变更.*?股份有限公司', '整体变更'),
        # 资本公积转增: "资本公积.*转增""资本公积金.*转增股本"
        (r'(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日).*?(?:资本公积(?:金)?.*?转增|未分配利润.*?转增)', '资本公积转增'),
    ]
    for pattern, ev_type in patterns:
        for m in re.finditer(pattern, text):
            date_str = normalize_date(m.group(1))
            ctx = text[max(0, m.start()-100):min(len(text), m.end()+500)]

            # 提取金额
            amt_match = re.search(r'(\d+[\d,]*\.?\d*)\s*万', ctx)
            amount = float(amt_match.group(1).replace(',', '')) if amt_match else None

            # 提取认购方(公司/机构实体)
            investors = list(set(re.findall(
                r'([一-龥]{2,25}(?:有限(?:责任)?公司|合伙企业|基金|创投|投资|集团|中心))', ctx)))

            # 找PDF页码
            page = 1
            pm = re.search(r'##\s*第(\d+)页', text[:m.start()])
            if pm:
                page = int(pm.group(1))

            for inv in investors[:3]:
                rows.append({
                    "record_type": "subscription_flow",
                    "company_name": full_name,
                    "stock_code": code,
                    "source_page": f"PDF p{page}",
                    "subscription_date": date_str,
                    "subscriber_name": inv,
                    "shares_subscribed": None,
                    "amount_subscribed": amount,
                    "price_per_share": None,
                    "event_context": ev_type,
                    "evidence_text": ctx[:500].strip(),
                    "notes": "auto_extracted_by_rules",
                })
    return rows


def extract_snapshots(text, full_name, code):
    """提取股权结构快照: 从MD文本中找股东持股信息"""
    rows = []
    # 找含股东信息的段落: 股东名称 + 持股比例模式
    # 模式: 股东名(2-20字) + 数字 + 万 + 数字%
    shareholder_pattern = re.compile(
        r'([一-龥]{2,20}(?:有限(?:责任)?公司|合伙企业|基金|创投|投资|集团|中心|管理)?)'
        r'.{0,20}?(\d+\.?\d*)%\s*(?:股权|股份|持股)?', re.MULTILINE)

    # 分段处理: 每个 ## 第N页 是一个段落
    sections = re.split(r'##\s*第(\d+)页', text)
    for i in range(1, len(sections), 2):
        page = sections[i]
        section_text = sections[i+1] if i+1 < len(sections) else ""

        # 检查是否是股权相关段落
        if not re.search(r'股东|持股|出资|股权结构|股本', section_text[:500]):
            continue

        # 尝试找日期
        date_match = re.search(r'(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日|\d{4}\s*年\s*\d{1,2}\s*月)', section_text)
        snap_date = normalize_date(date_match.group(1)) if date_match else ""

        seen_names = set()
        for m in shareholder_pattern.finditer(section_text):
            name = m.group(1).strip()
            ratio = m.group(2) + "%"

            if name in seen_names:
                continue
            seen_names.add(name)

            # 排除明显非股东名: 纯数字/过短/纯英文
            if len(name) < 2 or re.match(r'^\d+$', name):
                continue

            rows.append({
                "record_type": "equity_snapshot",
                "company_name": full_name,
                "stock_code": code,
                "source_page": f"PDF p{page}",
                "snapshot_date": snap_date,
                "snapshot_type": "auto_extracted",
                "total_shares": None,
                "total_capital": None,
                "shareholder_name": name,
                "shares_held": None,
                "capital_contribution": None,
                "shareholding_ratio": ratio,
                "evidence_text": section_text[:500].strip(),
                "notes": "auto_extracted_by_rules",
            })
        # 限制每页最多20条
        rows = rows[:-len(seen_names)] + rows[-min(len(seen_names), 20):]

    # 只保留有日期的记录 (无日期的股东列表无法关联到具体时点)
    return [r for r in rows if r["snapshot_date"]]


def main():
    print("=" * 60)
    print("[AUTO] extract_with_rules — 规则自动提取")
    print("=" * 60)

    all_flows, all_snaps, md_missing = [], [], []
    for name, info in TARGET_COMPANIES.items():
        text, full_name, code = read_company_md(name)
        if not text:
            md_missing.append(f"{name}({info['code']})")
            continue

        flows = extract_flows(text, full_name, code)
        snaps = extract_snapshots(text, full_name, code)
        all_flows.extend(flows)
        all_snaps.extend(snaps)
        print(f"  {name}: {len(flows)} flows + {len(snaps)} snaps")

    if md_missing:
        print(f"\n⚠ MD文件缺失 ({len(md_missing)}家): {', '.join(md_missing)}")
        print("  → 人工步骤: 下载PDF → python3 parse_pdf.py")

    # 写JSONL
    with open(AUTO_SF_JSONL, "w", encoding="utf-8") as f:
        for row in all_flows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    with open(AUTO_ES_JSONL, "w", encoding="utf-8") as f:
        for row in all_snaps:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    n_companies = len([n for n, _ in TARGET_COMPANIES.items() if read_company_md(n)[0]])
    print(f"\n✓ auto_subscription_flow.jsonl: {len(all_flows)} rows ({n_companies}/8 companies)")
    print(f"✓ auto_equity_snapshot.jsonl:  {len(all_snaps)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
