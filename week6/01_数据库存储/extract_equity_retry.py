"""
重新提取失败页面的股权快照
- 扩大搜索范围（目标页±2页）
- 文本+表格双模式
- 三协电机/星图测控/影石创新/赛分科技补全
"""
import json, re, sys, os
from pathlib import Path
import pdfplumber, fitz
import pg8000

# DB_CONFIG → from pipeline.db_config import DB_CONFIG
import sys; sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'pipeline'))
try:
    from db_config import DB_CONFIG
except ImportError:
    DB_CONFIG = {
    'host': '<server-host>', 'port': 5433, 'database': 'student',
    'user': '<redacted>', 'password': os.environ.get('DB_PASSWORD', ''),
}

PDF_DIR = Path('/Users/zhaobingqing/GitHub/prospectus-pevc-project/week1/data/week1PDF')

# 失败的页面（扩大搜索范围）
RETRY = {
    "920100": {  # 三协电机 p30-32
        "pdf": "三协电机_招股书_正式稿_20250711.pdf",
        "snapshots": [
            ("t0|深圳三协设立", 30), ("t1|第一次增资后", 31), ("t2|第二次增资后", 32),
        ]
    },
    "920116": {  # 星图测控 p44-48
        "pdf": "星图测控_招股书_正式稿_20241220.pdf",
        "snapshots": [
            ("t0|报告期初", 44), ("t1|代持还原后", 46), ("t2|第一次增资后", 48),
        ]
    },
    "688775": {  # 影石创新 p68
        "pdf": "影石创新_招股书_正式稿_20250606.pdf",
        "snapshots": [
            ("t1|2019年增资后", 68),
        ]
    },
    "603418": {  # 友升股份补充
        "pdf": "友升股份_招股书_正式稿_20250918.pdf",
        "snapshots": [
            ("t0+|整体变更后", 43),
        ]
    },
}

NAME_MAP = {
    "920100": "三协电机", "920116": "星图测控", "688775": "影石创新", "603418": "友升股份",
}


def classify(name):
    if not name or len(name) < 2: return '其他'
    if re.search(r'(政府|引导|国有|国家)', name): return '政府基金'
    if re.search(r'(有限|合伙|基金|创投|投资|中心|资本|达晨|高瓴|启明|IDG|深创投|东方富海|复星|国科|华泰|聚贝|金浦|杉|EARN|QM|CASREV)', name): return 'PE'
    if re.match(r'^[A-Z][A-Za-z0-9\s&]{2,30}$', name): return '外资基金'
    if re.match(r'^[一-龥]{2,4}$', name): return '自然人'
    return '其他'


def extract_shareholders_from_page(pdf_path, page_num):
    """从PDF页提取股东，先用pdfplumber表格，不行就用PyMuPDF文本模式"""
    results = []

    # 方法1: pdfplumber表格
    with pdfplumber.open(str(pdf_path)) as pdf:
        if page_num <= len(pdf.pages):
            page = pdf.pages[page_num - 1]
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    if not table or len(table) < 2: continue
                    # 找表头
                    hi = None
                    for i, row in enumerate(table):
                        rt = "".join([str(c) if c else "" for c in row])
                        if re.search(r'(股东|持股|股数|比例|姓名)', rt):
                            hi = i; break
                    if hi is None: continue
                    # 找名字列
                    nc = None
                    for j, h in enumerate(table[hi]):
                        if h and re.search(r'(股东|姓名|名称|投资人)', str(h)): nc = j; break
                    if nc is None: nc = 0  # 第一列大概率是名字

                    for row in table[hi+1:]:
                        if not row or len(row) <= nc: continue
                        name = str(row[nc]).strip() if row[nc] else ""
                        if not name or len(name) < 2: continue
                        if re.search(r'^(合计|总计|序号|—|、)', name): continue

                        # 尝试找股数和比例
                        shares = ratio = None
                        for j, cell in enumerate(row):
                            if j == nc: continue
                            v = str(cell).replace(',', '').strip() if cell else ""
                            if re.match(r'^[\d.]+%?$', v) and ratio is None:
                                m = re.search(r'([\d.]+)', v)
                                if m: ratio = float(m.group(1))
                            elif v.replace('.','').isdigit() and len(v) >= 3 and shares is None:
                                try: shares = float(v)
                                except: pass
                        results.append({'name': name[:200], 'shares': shares, 'ratio': ratio})

    if results: return results

    # 方法2: PyMuPDF文本提取 + 正则匹配股东名+持股比例
    doc = fitz.open(str(pdf_path))
    if page_num <= len(doc):
        text = doc[page_num - 1].get_text("text")
        # 匹配模式: 股东名(2-20字) + 数字 + % 或 万股
        pattern = r'([一-龥A-Za-z]{2,20}(?:有限(?:责任)?公司|合伙企业|基金|创投|投资|中心)?)\s+([\d,]+\.?\d*)\s*(万股|%)?\s*([\d.]+%)?'
        for m in re.finditer(pattern, text):
            name = m.group(1).strip()
            if name in ('发行人基本情况', '注册资本', '总股本', '本次发行前', '本次发行后'):
                continue
            ratio = None
            if m.group(4):
                rm = re.search(r'([\d.]+)', m.group(4))
                if rm: ratio = float(rm.group(1))
            shares = None
            if m.group(2) and '万股' in (m.group(3) or ''):
                try: shares = float(m.group(2).replace(',',''))
                except: pass
            results.append({'name': name[:200], 'shares': shares, 'ratio': ratio})

    doc.close()
    return results


def main():
    conn = pg8000.connect(**DB_CONFIG)
    cur = conn.cursor()
    total = 0

    for code, info in RETRY.items():
        name = NAME_MAP[code]
        pdf_path = PDF_DIR / info["pdf"]
        if not pdf_path.exists():
            print(f"  SKIP {code}: PDF不存在")
            continue

        print(f"\n📄 {name} ({code})")

        for label, pg in info["snapshots"]:
            # 扩大搜索: pg-2 到 pg+2
            found = False
            for scan_pg in range(pg - 2, pg + 3):
                if scan_pg < 1: continue
                shs = extract_shareholders_from_page(pdf_path, scan_pg)
                if shs:
                    print(f"  ✅ {label} p{pg} → 实际在p{scan_pg}找到 {len(shs)} 名股东")
                    for sh in shs:
                        cur.execute("""
                            INSERT INTO zbq_equity_snapshot
                                (event_id, company_name, stock_code, snapshot_label, snapshot_date,
                                 shareholder_name, shares_wan, shareholding_pct,
                                 shareholder_type, pdf_page,
                                 evidence_text, extraction_notes, review_status)
                            VALUES (%s,%s,%s,%s,%s, %s,%s,%s, %s,%s, %s,%s,%s)
                        """, (
                            f"{code}_es_retry_{total:04d}", name, code,
                            label[:50], "2025-07-11",
                            sh['name'], sh['shares'], sh['ratio'],
                            classify(sh['name']), scan_pg,
                            f"独立PDF提取 p{scan_pg}: {sh['name']}",
                            f"retry {label}快照（原目标p{pg}）",
                            'extracted',
                        ))
                        total += 1
                    found = True
                    break
            if not found:
                print(f"  ⚠ {label} p{pg}±2: PDF该区域无可提取的文本表格（可能为图片格式）")

    conn.commit()
    cur.execute("SELECT COUNT(*) FROM zbq_equity_snapshot")
    zbq = cur.fetchone()[0]
    print(f"\n总计新增: {total} 条")
    print(f"zbq_equity_snapshot: {zbq}")
    conn.close()


if __name__ == "__main__":
    main()
