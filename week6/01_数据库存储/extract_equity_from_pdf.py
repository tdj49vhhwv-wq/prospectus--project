"""
从PDF指定页提取股权快照 — 学习ymx的多快照模式
每家公司提取3-5个历史快照点（对标ymx的snapshot_label分布）
"""
import json, re, sys, os
from pathlib import Path

import pdfplumber, pg8000

# DB_CONFIG → from pipeline.db_config import DB_CONFIG
import sys; sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'pipeline'))
try:
    from db_config import DB_CONFIG
except ImportError:
    DB_CONFIG = {
    'host': '<server-host>', 'port': 5433, 'database': 'student',
    'user': '<redacted>', 'password': os.environ.get('DB_PASSWORD', ''),
}

WEEK6 = Path(__file__).resolve().parent.parent
PROJECT = WEEK6.parent
PDF_DIR = PROJECT / "week1" / "data" / "week1PDF"

# ymx发现的每公司快照页码（逐页提取表格）
SNAPSHOT_PAGES = {
    "001282": [  # 三联锻造
        ("t0|报告期初", 36, "2023-05-17"),
        ("t1|第一次增资后", 37, "2023-05-17"),
    ],
    "301563": [  # 云汉芯城（跳过OCR需要的流程图片页）
        ("s1|2018年4月第一次股权转让后", 58, "2025-09-25"),
        ("s2|2018年7月第一次增资后", 60, "2025-09-25"),
        ("s3|2020年5月第二次增资后", 62, "2025-09-25"),
        ("s4|2020年9月第三次增资后", 64, "2025-09-25"),
    ],
    "301581": [  # 黄山谷捷
        ("t1|第一次股权转让后", 40, "2024-12-19"),
        ("t2|第一次增资后", 42, "2024-12-19"),
        ("t3|第二次增资后", 44, "2024-12-19"),
    ],
    "603418": [  # 友升股份
        ("t0|报告期初", 44, "2025-09-18"),
        ("t1|2020-09-30增资后", 44, "2025-09-18"),
        ("t2|2022-12-19增资后", 45, "2025-09-18"),
    ],
    "688758": [  # 赛分科技
        ("t_setup|2009年公司设立", 51, "2025-01-06"),
        ("t0|报告期初", 50, "2025-01-06"),
        ("t1|第一次增资后", 51, "2025-01-06"),
        ("t_restructure|2021年整体变更后", 52, "2025-01-06"),
    ],
    "688775": [  # 影石创新
        ("t0|报告期初", 65, "2025-06-06"),
        ("t1|2019年增资后", 68, "2025-06-06"),
        ("t2|2020年增资后", 72, "2025-06-06"),
    ],
    "920100": [  # 三协电机
        ("t0|深圳三协设立", 30, "2025-07-11"),
        ("t1|第一次增资后", 31, "2025-07-11"),
        ("t2|第二次增资后", 32, "2025-07-11"),
    ],
    "920116": [  # 星图测控
        ("t0|报告期初", 44, "2024-12-20"),
        ("t1|代持还原后", 46, "2024-12-20"),
        ("t2|第一次增资后", 48, "2024-12-20"),
        ("t3|股权激励后", 50, "2024-12-20"),
        ("t4|第二次增资后", 51, "2024-12-20"),
    ],
}

COMPANY_NAMES = {
    "001282": "三联锻造", "301563": "云汉芯城", "301581": "黄山谷捷",
    "603418": "友升股份", "688758": "赛分科技", "688775": "影石创新",
    "920100": "三协电机", "920116": "星图测控",
}


def classify_investor(name):
    if not name or len(name) < 2: return '其他'
    if re.search(r'(政府|引导|国有|国家)', name): return '政府基金'
    if re.search(r'(天使|种子|孵化)', name): return 'VC'
    if re.search(r'(有限|合伙|基金|创投|投资|集团|中心|资本|资产|达晨|高瓴|启明|IDG|深创投|东方富海|复星|国科|华泰|聚贝|金浦|杉|EARN|QM|CASREV)', name): return 'PE'
    if re.match(r'^[A-Z][A-Za-z0-9\s&]{2,30}$', name): return '外资基金'
    if re.match(r'^[一-龥]{2,4}$', name): return '自然人'
    return '其他'


def extract_table_shareholders(pdf_path, page_num):
    """从PDF指定页提取股东持股表"""
    shareholders = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        if page_num > len(pdf.pages):
            return shareholders
        page = pdf.pages[page_num - 1]
        tables = page.extract_tables()
        if not tables:
            return shareholders

        for table in tables:
            if not table or len(table) < 2:
                continue
            # 找表头：含"股东"或"持股"关键字的行
            header_idx = None
            for i, row in enumerate(table):
                row_text = "".join([str(c) if c else "" for c in row])
                if re.search(r'(股东|持股|股数|比例)', row_text):
                    header_idx = i
                    break
            if header_idx is None:
                continue

            # 确定列：名字列、股数列、比例列
            header = [str(c).strip() if c else "" for c in table[header_idx]]
            name_col = shares_col = ratio_col = None
            for j, h in enumerate(header):
                if re.search(r'(股东|姓名|名称|投资人)', h) and name_col is None:
                    name_col = j
                elif re.search(r'(股数|持股数量|股份)', h) and shares_col is None:
                    shares_col = j
                elif re.search(r'(比例|%)', h) and ratio_col is None:
                    ratio_col = j

            if name_col is None:
                continue

            for row in table[header_idx + 1:]:
                if not row or len(row) <= (name_col or 0):
                    continue
                name = str(row[name_col]).strip() if row[name_col] else ""
                if not name or len(name) < 2:
                    continue
                # 排除非股东行
                if re.search(r'^(?:合\s*计|总\s*计|序号|股东姓?名|—|$)', name):
                    continue

                shares = ratio = None
                if shares_col is not None and len(row) > shares_col:
                    val = str(row[shares_col]).replace(',', '').strip() if row[shares_col] else ""
                    try:
                        shares = float(val) if val else None
                    except: pass
                if ratio_col is not None and len(row) > ratio_col:
                    val = str(row[ratio_col]).strip() if row[ratio_col] else ""
                    if val and re.search(r'\d', val):
                        m = re.search(r'([\d.]+)\s*%?', val)
                        if m: ratio = float(m.group(1))

                shareholders.append({
                    'name': name[:200],
                    'shares': shares,
                    'ratio': ratio,
                })

    return shareholders


def main():
    conn = pg8000.connect(**DB_CONFIG)
    cur = conn.cursor()

    print("=" * 60)
    print("PDF股权快照提取 — 对标ymx多快照模式")
    print("=" * 60)

    total = 0
    for code, snapshots in SNAPSHOT_PAGES.items():
        name = COMPANY_NAMES[code]
        # 直接匹配PDF: 三联锻造_招股书_正式稿_20230517.pdf
        pdf_date = snapshots[0][2].replace('-', '')
        pdf_file = PDF_DIR / f"{name}_招股书_正式稿_{pdf_date}.pdf"
        if not pdf_file.exists():
            matches = list(PDF_DIR.glob(f"{name}*.pdf"))
            if matches:
                pdf_file = matches[0]
            else:
                print(f"  SKIP {code} {name}: PDF不存在 ({pdf_file})")
                continue

        print(f"\n{'='*40}")
        print(f"📄 {name} ({code}) → {pdf_file.name}")
        print(f"  快照点: {len(snapshots)} 个")

        for label, page, _ in snapshots:
            shareholders = extract_table_shareholders(pdf_file, page)
            if not shareholders:
                print(f"    ⚠ {label} p{page}: 未找到股东表")
                continue

            print(f"    ✅ {label} p{page}: {len(shareholders)} 名股东")
            for sh in shareholders:
                cur.execute("""
                    INSERT INTO zbq_equity_snapshot
                        (event_id, company_name, stock_code, snapshot_label, snapshot_date,
                         shareholder_name, shares_wan, shareholding_pct,
                         shareholder_type, pdf_page,
                         evidence_text, extraction_notes, review_status)
                    VALUES (%s,%s,%s,%s,%s, %s,%s,%s, %s,%s, %s,%s,%s)
                """, (
                    f"{code}_es_pdf_{total:04d}",
                    name, code,
                    label[:50], snapshots[0][2],
                    sh['name'], sh['shares'], sh['ratio'],
                    classify_investor(sh['name']),
                    page,
                    f"pdfplumber提取 p{page} 表格行: {sh['name']}",
                    f"对标ymx {label}快照",
                    'extracted',
                ))
                total += 1

    conn.commit()

    # 更新统计
    cur.execute("""
        UPDATE zbq_companies c SET
            snapshot_count = (SELECT COUNT(*) FROM zbq_equity_snapshot WHERE stock_code = c.company_id)
    """)
    conn.commit()

    print(f"\n{'='*60}")
    print(f"总计: {total} 条股权快照")
    cur.execute("SELECT COUNT(*) FROM zbq_equity_snapshot")
    print(f"zbq_equity_snapshot 总数: {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM ymx_equity_snapshot")
    ymx_cnt = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM zbq_equity_snapshot")
    zbq_cnt = cur.fetchone()[0]
    print(f"ymx_equity_snapshot: {ymx_cnt}")
    print(f"对比: zbq={zbq_cnt} vs ymx={ymx_cnt} ({zbq_cnt/ymx_cnt*100:.0f}%)")

    conn.close()
    print("\nOK!")


if __name__ == "__main__":
    main()
