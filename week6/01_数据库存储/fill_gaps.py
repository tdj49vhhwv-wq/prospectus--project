"""
精准补刀: 针对最高缺口页面深度提取

影石创新p72(缺76人) / 云汉芯城p64(缺56人) /
赛分科技p51(缺39人) / 友升股份p45(缺34人) / 赛分科技p50(缺32人)
"""
import re, os, sys
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

# 高优先级缺口页面（页码, 快照标签, PDF文件名, 公司代码, 公司名）
HIGH_PRIORITY = [
    # 影石创新 p72: 78人快照只抓到2人
    (72, "t2|2020年增资后", "影石创新_招股书_正式稿_20250606.pdf", "688775", "影石创新"),
    # 云汉芯城 p64: 68人快照只抓到12人
    (64, "s4|2020年9月第三次增资后", "云汉芯城_招股书_正式稿_20250925.pdf", "301563", "云汉芯城"),
    # 赛分科技 p51: 42人快照只抓到3人
    (51, "t1|第一次增资后", "赛分科技_招股书_正式稿_20250106.pdf", "688758", "赛分科技"),
    # 赛分科技 p50: 32人快照没抓到
    (50, "t0|报告期初", "赛分科技_招股书_正式稿_20250106.pdf", "688758", "赛分科技"),
    # 友升股份 p45: 34人快照没抓到
    (45, "t2|2022-12-19增资后", "友升股份_招股书_正式稿_20250918.pdf", "603418", "友升股份"),
    # 影石创新 p68: 58人快照只抓到16人
    (68, "t1|2019年增资后", "影石创新_招股书_正式稿_20250606.pdf", "688775", "影石创新"),
    # 云汉芯城 p60: 48人快照只抓到14人
    (60, "s2|2018年7月第一次增资后", "云汉芯城_招股书_正式稿_20250925.pdf", "301563", "云汉芯城"),
]

def classify(name):
    if not name or len(name) < 2: return '其他'
    if re.search(r'(政府|引导|国有|国家)', name): return '政府基金'
    if re.search(r'(有限|合伙|基金|创投|投资|中心|达晨|高瓴|启明|IDG|深创投|东方富海|复星|国科|华泰|聚贝|金浦|杉|EARN|QM|CASREV)', name): return 'PE'
    if re.match(r'^[A-Z][A-Za-z0-9\s&]{2,30}$', name): return '外资基金'
    if re.match(r'^[一-龥]{2,4}$', name): return '自然人'
    return '其他'


def deep_extract_page(pdf_path, target_page):
    """
    深度提取: 扫描目标页±1页，用pdfplumber+fitz双引擎
    处理合并单元格: 空值继承上一行
    """
    results = []

    for pg in [target_page - 1, target_page, target_page + 1]:
        if pg < 1: continue

        # 引擎1: pdfplumber
        with pdfplumber.open(str(pdf_path)) as pdf:
            if pg > len(pdf.pages): continue
            page = pdf.pages[pg - 1]
            tables = page.extract_tables()
            for table in tables:
                if not table or len(table) < 3: continue
                for row in table:
                    sh = _parse_row_for_shareholder(row, pg)
                    if sh: results.append(sh)

        # 引擎2: PyMuPDF文本模式
        doc = fitz.open(str(pdf_path))
        if pg <= len(doc):
            text = doc[pg - 1].get_text("text")
            # 文本模式: 匹配"股东名 + 数字 + %"模式
            for m in re.finditer(
                r'([一-龥A-Za-z]{2,30}(?:有限(?:责任)?公司|合伙企业|基金|创投|投资|中心|管理|集团)?)\s+'
                r'([\d,]+\.?\d*)\s*(万股|万元)?\s*([\d.]+%)?',
                text
            ):
                name = m.group(1).strip()
                if name in ('发行人基本情况','注册资本','总股本','本次发行前','本次发行后'): continue
                ratio = None
                if m.group(4):
                    rm = re.search(r'([\d.]+)', m.group(4))
                    if rm: ratio = float(rm.group(1))
                shares = None
                if '万股' in (m.group(3) or ''):
                    try: shares = float(m.group(2).replace(',',''))
                    except: pass
                results.append({'name': name[:200], 'shares': shares, 'ratio': ratio, 'page': pg, 'method': 'pymupdf_text'})
        doc.close()

    # 去重 (同股东名只保留一次)
    seen = set()
    unique = []
    for r in results:
        if r['name'] not in seen:
            seen.add(r['name'])
            unique.append(r)
    return unique


def _parse_row_for_shareholder(row, page):
    """从表格行提取股东信息"""
    row_text = ' | '.join([str(c).strip() if c else '' for c in row])
    # 找名字(2-20个中英文字符)
    for cell in row:
        name = str(cell).strip() if cell else ''
        if not name or len(name) < 2: continue
        if re.search(r'^(合计|总计|序号|—|、|股东名称|姓\s*名)$', name): continue
        if not re.match(r'^[一-龥A-Za-z0-9\s\.\-]+$', name): continue
        if len(name) > 30: continue

        # 找股数和比例
        shares = ratio = None
        for c in row:
            v = str(c).replace(',','').strip() if c else ''
            if re.match(r'^[\d.]+%?$', v) and ratio is None:
                m = re.search(r'([\d.]+)', v)
                if m: ratio = float(m.group(1))
            elif v.replace('.','').isdigit() and len(v)>=3 and shares is None:
                try: shares = float(v)
                except: pass

        return {'name': name[:200], 'shares': shares, 'ratio': ratio, 'page': page, 'method': 'pdfplumber_table'}
    return None


def main():
    conn = pg8000.connect(**DB_CONFIG)
    cur = conn.cursor()
    total = 0

    for page, label, pdf_name, code, name in HIGH_PRIORITY:
        pdf_path = PDF_DIR / pdf_name
        if not pdf_path.exists():
            print(f"  SKIP: {pdf_name}")
            continue

        print(f"\n📄 {name}({code}) {label} p{page}")
        shareholders = deep_extract_page(pdf_path, page)
        print(f"  找到 {len(shareholders)} 名股东")

        for sh in shareholders:
            cur.execute("""
                INSERT INTO zbq_equity_snapshot
                    (event_id, company_name, stock_code, snapshot_label, snapshot_date,
                     shareholder_name, shares_wan, shareholding_pct,
                     shareholder_type, pdf_page,
                     evidence_text, extraction_notes, review_status)
                VALUES (%s,%s,%s,%s,%s, %s,%s,%s, %s,%s, %s,%s,%s)
            """, (
                f"{code}_es_gap_{total:04d}", name, code,
                label[:50], "2025-07-01",
                sh['name'], sh['shares'], sh['ratio'],
                classify(sh['name']), sh['page'],
                f"depth_extract p{sh['page']} {sh['method']}: {sh['name']}",
                f"精准补刀 {label}快照 (原缺{code})",
                'extracted',
            ))
            total += 1

    conn.commit()
    cur.execute("SELECT COUNT(*) FROM zbq_equity_snapshot")
    z = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM ymx_equity_snapshot")
    y = cur.fetchone()[0]
    print(f"\n{'='*60}")
    print(f"精准补刀: +{total} 条")
    print(f"zbq={z} vs ymx={y} ({z/y*100:.0f}%)")
    conn.close()


if __name__ == "__main__":
    main()
