"""
Week 6 — 全量导入脚本
从 auto_output/ JSONL + final/ 事件总表 → PostgreSQL zbq 系列表
对标同学（ymx/lyx/lzr）的完整字段结构
"""
import json
import re
import os
import sys
from pathlib import Path
from datetime import datetime

import pg8000

# DB_CONFIG → from pipeline.db_config import DB_CONFIG
import sys; sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'pipeline'))
try:
    from db_config import DB_CONFIG
except ImportError:
    DB_CONFIG = {
    'host': os.environ.get('DB_HOST', '<server-host>'),
    'port': int(os.environ.get('DB_PORT', '5433')),
    'database': os.environ.get('DB_NAME', 'student'),
    'user': os.environ.get('DB_USER', '<redacted>'),
    'password': os.environ.get('DB_PASSWORD', ''),
}

WEEK6 = Path(__file__).resolve().parent.parent
AUTO_OUTPUT = WEEK6 / "auto_output"
FINAL_DIR = WEEK6 / "final"

COMPANIES = [
    ("001282", "三联锻造"),
    ("301563", "云汉芯城"),
    ("301581", "黄山谷捷"),
    ("603418", "友升股份"),
    ("688758", "赛分科技"),
    ("688775", "影石创新"),
    ("920100", "三协电机"),
    ("920116", "星图测控"),
]


def connect():
    return pg8000.connect(**DB_CONFIG)


def load_jsonl(path):
    """加载JSONL文件"""
    rows = []
    if not path.exists():
        print(f"  SKIP: {path} 不存在")
        return rows
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return rows


def safe_float(val):
    """安全转为float"""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        # 尝试从字符串提取
        if isinstance(val, str):
            nums = re.findall(r'[\d,]+\.?\d*', val.replace(',', ''))
            if nums:
                try:
                    return float(nums[0].replace(',', ''))
                except:
                    pass
        return None


def import_companies(cur, conn):
    """导入公司清单"""
    print("\n[1/6] 导入公司清单...")
    data = [
        ("001282", "三联锻造", "深主板", "20230517"),
        ("301563", "云汉芯城", "创业板", "20250925"),
        ("301581", "黄山谷捷", "创业板", "20241219"),
        ("603418", "友升股份", "沪主板", "20250918"),
        ("688758", "赛分科技", "科创板", "20250106"),
        ("688775", "影石创新", "科创板", "20250606"),
        ("920100", "三协电机", "北交所", "20250711"),
        ("920116", "星图测控", "北交所", "20241220"),
    ]
    for code, name, board, pdf_date in data:
        cur.execute("""
            INSERT INTO zbq_companies (company_id, company_name, stock_code, ipo_board, pdf_prospectus_date, build_status, raw_data)
            VALUES (%s, %s, %s, %s, %s, 'built', '{}'::jsonb)
            ON CONFLICT (company_id) DO UPDATE SET
                ipo_board = EXCLUDED.ipo_board,
                build_status = 'built'
        """, (code, name, code, board, pdf_date))
    conn.commit()
    print(f"  OK: {len(data)} 家公司")


def import_equity_snapshots(cur, conn):
    """从 auto_output/{code}/equity_snapshot.jsonl 导入，兼容新旧两种格式"""
    print("\n[2/6] 导入股权快照...")
    total = 0
    skipped = 0
    for code, name in COMPANIES:
        path = AUTO_OUTPUT / code / "equity_snapshot.jsonl"
        rows = load_jsonl(path)
        for r in rows:
            # 兼容旧字段名 (shareholder) 和新字段名 (shareholder_name)
            sh_name = r.get("shareholder_name") or r.get("shareholder") or ""
            # 跳过明显非股东名的行（纯数字、财务指标等）
            if re.match(r'^[\d,.\s]+$', sh_name) or sh_name in (
                "最近一年及一期末总资产", "最近一年及一期末净资产",
                "最近一年及一期净利润", "是否经过审计", "审计机构名称",
                "总资产", "净资产", "净利润",
            ):
                skipped += 1
                continue
            if not sh_name or len(sh_name) < 2:
                skipped += 1
                continue

            cur.execute("""
                INSERT INTO zbq_equity_snapshot
                    (event_id, company_name, stock_code, snapshot_label, snapshot_date,
                     trigger_event, total_shares_wan, registered_capital_wan,
                     shareholder_name, shares_wan, shares_raw, shareholding_pct,
                     capital_wan, shareholder_type, shareholder_category,
                     pdf_page, evidence_text, extraction_notes, review_status)
                VALUES (%s,%s,%s,%s,%s, %s,%s,%s, %s,%s,%s,%s, %s,%s,%s, %s,%s,%s,%s)
            """, (
                r.get("event_id"),
                name, code,
                r.get("snapshot_type"),
                r.get("snapshot_date"),
                r.get("trigger_event"),
                r.get("total_shares"),
                r.get("total_capital"),
                sh_name,
                safe_float(r.get("shares_held")),
                str(r.get("shares_held")) if r.get("shares_held") else None,
                _parse_pct(r.get("shareholding_ratio")),
                r.get("capital_contribution"),
                r.get("shareholder_type_detail") or r.get("investor_type") or _classify_type(sh_name),
                None,
                r.get("pdf_page") or _parse_page(r.get("source_page") or r.get("page")),
                r.get("evidence_text") or r.get("evidence") or "",
                r.get("notes") or r.get("status_detail") or f"source={r.get('source','')}",
                r.get("processing_status", "extracted"),
            ))
            total += 1
    conn.commit()
    print(f"  OK: {total} 条快照记录 (跳过 {skipped} 条无效数据)")


def import_subscription_flows(cur, conn):
    """从 auto_output/{code}/subscription_flow.jsonl 或 extracted_events.jsonl 导入"""
    print("\n[3/6] 导入认缴流量...")
    total = 0
    for code, name in COMPANIES:
        path = AUTO_OUTPUT / code / "subscription_flow.jsonl"
        if not path.exists():
            path = AUTO_OUTPUT / code / "extracted_events.jsonl"
        rows = load_jsonl(path)
        for r in rows:
            # 兼容新旧两种格式
            event_id = r.get("event_id") or f"{code}_sf_{total:03d}"
            ev_type = r.get("event_context") or r.get("type") or r.get("rule") or ""
            ev_date = r.get("subscription_date") or r.get("date") or ""
            # date可能是数组（旧格式），取第一个
            if isinstance(ev_date, list):
                ev_date = ev_date[0] if ev_date else ""
            investor = r.get("subscriber_name") or r.get("party") or r.get("investor") or ""
            if not investor:
                # 从evidence或rule中推测
                inv_raw = r.get("investors_raw", [])
                if isinstance(inv_raw, list) and inv_raw:
                    investor = ", ".join(inv_raw[:5])
            if not investor or len(str(investor)) < 1:
                investor = "（待识别）"

            cur.execute("""
                INSERT INTO zbq_subscription_flow
                    (event_id, company_name, stock_code, event_type, event_date,
                     investor_name, investor_type,
                     subscription_qty_wan, subscription_qty_raw,
                     subscription_amount_wan, subscription_amount_raw,
                     subscription_price, subscription_price_raw,
                     registered_capital_before, registered_capital_after,
                     currency, pdf_page, evidence_text, extraction_method, review_status)
                VALUES (%s,%s,%s,%s,%s, %s,%s, %s,%s, %s,%s, %s,%s, %s,%s, %s,%s,%s,%s,%s)
            """, (
                event_id, name, code,
                ev_type, str(ev_date)[:20] if ev_date else None,
                str(investor)[:200] if investor else "（待识别）",
                r.get("investor_type") or _classify_type(str(investor)),
                safe_float(r.get("shares_subscribed")),
                str(r.get("shares_subscribed")) if r.get("shares_subscribed") else str(r.get("shares") or ""),
                safe_float(r.get("amount_subscribed")),
                str(r.get("amount_subscribed")) if r.get("amount_subscribed") else str(r.get("amount") or ""),
                safe_float(r.get("price_per_share")),
                str(r.get("price_per_share")) if r.get("price_per_share") else str(r.get("price") or ""),
                None, None, 'CNY',
                r.get("pdf_page") or _parse_page(r.get("source_page") or r.get("page")),
                r.get("evidence_text") or r.get("evidence") or "",
                r.get("source") or r.get("extraction_method") or "auto",
                r.get("processing_status", "extracted") if r.get("processing_status") else (
                    "manual_review" if investor == "（待识别）" else "extracted"
                ),
            ))
            total += 1
    conn.commit()
    print(f"  OK: {total} 条认缴记录")


def import_share_transfers(cur, conn):
    """从 auto_output/{code}/share_transfer.jsonl 导入"""
    print("\n[4/6] 导入股权转让...")
    total = 0
    for code, name in COMPANIES:
        path = AUTO_OUTPUT / code / "share_transfer.jsonl"
        rows = load_jsonl(path)
        for r in rows:
            cur.execute("""
                INSERT INTO zbq_share_transfer_flow
                    (event_id, company_name, stock_code, event_date, event_type,
                     transferor_name, transferee_name, participant_type,
                     transfer_qty_wan, transfer_qty_raw,
                     transfer_amount_wan, transfer_amount_raw,
                     transfer_price, currency, pdf_page, evidence_text,
                     extraction_method, review_status)
                VALUES (%s,%s,%s,%s,%s, %s,%s,%s, %s,%s, %s,%s, %s,%s,%s,%s, %s,%s)
            """, (
                r.get("event_id"),
                name, code,
                r.get("transfer_date") or r.get("date"),
                r.get("transfer_type") or r.get("event_type"),
                r.get("transferor_name"),
                r.get("transferee_name"),
                _classify_type(str(r.get("transferor_name", ""))),
                safe_float(r.get("shares_transferred")),
                str(r.get("shares_transferred")) if r.get("shares_transferred") else None,
                safe_float(r.get("transfer_amount")),
                str(r.get("transfer_amount")) if r.get("transfer_amount") else None,
                safe_float(r.get("price_per_share")),
                'CNY',
                _parse_page(r.get("source_page")),
                r.get("evidence_text"),
                r.get("source") or "auto",
                r.get("processing_status", "extracted"),
            ))
            total += 1
    conn.commit()
    print(f"  OK: {total} 条转让记录")


def import_pe_fund_details(cur, conn):
    """从 auto_output/{code}/pe_fund_detail.jsonl 导入"""
    print("\n[5/6] 导入PE基金详情...")
    total = 0
    for code, name in COMPANIES:
        path = AUTO_OUTPUT / code / "pe_fund_detail.jsonl"
        rows = load_jsonl(path)
        for r in rows:
            cur.execute("""
                INSERT INTO zbq_pe_fund_detail
                    (event_id, company_name, stock_code, fund_name, fund_type,
                     filing_code, filing_date, fund_manager, manager_filing_code,
                     gp_name, lp_names, fund_size_wan,
                     shareholding_ratio, shares_held_wan,
                     pdf_page, evidence_text, confidence, review_status)
                VALUES (%s,%s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s, %s,%s, %s,%s,%s,%s)
            """, (
                r.get("event_id"),
                name, code,
                r.get("fund_name"),
                r.get("fund_type"),
                r.get("filing_code"),
                r.get("filing_date"),
                r.get("fund_manager"),
                r.get("manager_filing_code"),
                r.get("gp_name"),
                json.dumps(r.get("lp_names", []), ensure_ascii=False) if r.get("lp_names") else '[]',
                r.get("fund_size"),
                r.get("shareholding_ratio"),
                safe_float(r.get("shares_held")),
                _parse_page(r.get("source_page")),
                r.get("evidence_text"),
                0.7,  # confidence
                r.get("processing_status", "extracted"),
            ))
            total += 1
    conn.commit()
    print(f"  OK: {total} 条基金记录")


def import_cross_checks(cur, conn):
    """从 final/ 事件总表生成 cross_check 记录"""
    print("\n[6/6] 导入交叉验证...")
    md_path = FINAL_DIR / "八家公司融资事件总表.md"
    if not md_path.exists():
        print("  SKIP: 事件总表不存在")
        return

    with open(md_path) as f:
        content = f.read()

    total = 0
    # 解析markdown表格
    for line in content.split('\n'):
        line = line.strip()
        if not line.startswith('|') or '日期' in line or '---' in line:
            continue
        cols = [c.strip() for c in line.split('|')[1:-1]]
        if len(cols) < 7:
            continue
        date, company, ev_type, investor, amt_price, difficulty, evidence = cols[:7]

        # 提取股票代码
        code_match = re.search(r'\((\d{6})\)', company)
        code = code_match.group(1) if code_match else ""
        name = re.sub(r'\(\d{6}\)', '', company).strip()

        # 难度映射为 check_result
        result_map = {"✅": "pass", "⚠": "pending_review", "🔴": "mismatch"}
        check_result = result_map.get(difficulty, "pending_review")

        cur.execute("""
            INSERT INTO zbq_cross_check
                (company_name, stock_code, check_point,
                 flow_event_type,
                 notes, evidence_pdf_page, check_result)
            VALUES (%s,%s,%s, %s, %s,%s, %s)
        """, (
            name, code,
            f"{date} {investor}",
            ev_type,
            f"金额/价格: {amt_price}",
            _parse_page(evidence),
            check_result,
        ))
        total += 1

    conn.commit()
    print(f"  OK: {total} 条交叉验证记录")


def _parse_pct(val):
    """解析百分比: '62.97%' → 62.97"""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    m = re.search(r'([\d.]+)\s*%?', str(val))
    return float(m.group(1)) if m else None


def _parse_page(val):
    """解析页码: 'PDF p35' → 35"""
    if val is None:
        return None
    if isinstance(val, int):
        return val
    m = re.search(r'p(\d+)', str(val))
    return int(m.group(1)) if m else None


def _classify_type(name):
    """投资人类型分类"""
    if not name:
        return None
    if re.search(r'(有限|合伙|基金|创投|投资|集团|中心|资本|资产)', name):
        if re.search(r'(政府|引导|国有|国家)', name):
            return "政府基金"
        if re.search(r'(天使|种子|孵化)', name):
            return "VC"
        return "PE"
    if re.match(r'^[A-Z][A-Za-z0-9\s&]{2,20}$', name.strip()):
        return "外资基金"
    if re.match(r'^[一-龥]{2,4}$', name.strip()):
        return "自然人"
    return "其他"


def update_counts(cur, conn):
    """更新 zbq_companies 中各公司的记录数统计"""
    print("\n更新统计...")
    for code, name in COMPANIES:
        cur.execute("SELECT COUNT(*) FROM zbq_equity_snapshot WHERE stock_code=%s", (code,))
        snap = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM zbq_subscription_flow WHERE stock_code=%s", (code,))
        sub = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM zbq_share_transfer_flow WHERE stock_code=%s", (code,))
        trans = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM zbq_pe_fund_detail WHERE stock_code=%s", (code,))
        pe = cur.fetchone()[0]
        # 从主表取事件数
        cur.execute("SELECT COUNT(*) FROM zbq WHERE company LIKE %s", (f"%{code}%",))
        ev = cur.fetchone()[0]
        cur.execute("""
            UPDATE zbq_companies SET
                event_count=%s, snapshot_count=%s, subscription_count=%s,
                transfer_count=%s, pe_fund_count=%s
            WHERE company_id=%s
        """, (ev, snap, sub, trans, pe, code))
    conn.commit()


def main():
    conn = connect()
    cur = conn.cursor()
    print("=" * 60)
    print(f"Week 6 — 全量数据导入 {datetime.now():%Y-%m-%d %H:%M:%S}")
    print("=" * 60)

    # 清空旧数据
    for t in ["zbq_companies", "zbq_equity_snapshot", "zbq_subscription_flow",
              "zbq_share_transfer_flow", "zbq_cross_check", "zbq_pe_fund_detail"]:
        cur.execute(f"DELETE FROM {t}")
    conn.commit()
    print("旧数据已清空")

    import_companies(cur, conn)
    import_equity_snapshots(cur, conn)
    import_subscription_flows(cur, conn)
    import_share_transfers(cur, conn)
    import_pe_fund_details(cur, conn)
    import_cross_checks(cur, conn)
    update_counts(cur, conn)

    # 总览
    print("\n" + "=" * 60)
    print("导入完成！各表记录数:")
    for t in ["zbq_companies", "zbq_equity_snapshot", "zbq_subscription_flow",
              "zbq_share_transfer_flow", "zbq_pe_fund_detail", "zbq_cross_check"]:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        print(f"  {t}: {cur.fetchone()[0]} 条")

    conn.close()
    print("\nOK: 所有数据已导入!")


if __name__ == "__main__":
    main()
