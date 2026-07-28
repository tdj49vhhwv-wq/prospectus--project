"""
P1: PE基金详情扩展 v2 — 解析"私募基金备案情况"表格

赛分科技p86有完整PE备案表，其他公司同理
格式: 序号 | 股东名称 | 是否备案 | 备案时间 | 基金编号/产品编码
"""
import re, os
from pathlib import Path
import pdfplumber
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

# 每家公司PE备案表所在页（通过搜索"备案编码"或"基金编号"定位）
PE_PAGES = {
    "688758": ("赛分科技", "赛分科技_招股书_正式稿_20250106.pdf", 86),
    "920100": ("三协电机", "三协电机_招股书_正式稿_20250711.pdf", 34),  # 稳正景明
    # 其他公司需要搜索确认页码
}


def parse_pe_table(pdf_path, page_num):
    """从PDF页面解析PE备案表格"""
    results = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        if page_num > len(pdf.pages): return results
        page = pdf.pages[page_num - 1]
        tables = page.extract_tables()
        text = page.extract_text() or ""

    # 方法1: 解析表格
    for table in (tables or []):
        if not table or len(table) < 2: continue
        header = " ".join([str(c) if c else "" for c in table[0]])
        if not re.search(r'(股东|备案|基金|编码)', header): continue

        for row in table[1:]:
            cells = [str(c).strip() if c else "" for c in row]
            line = " | ".join(cells)
            # 找: 序号 | 名称 | 是否备案 | 备案时间 | 编码
            # 找基金名(不含"序号""合计"的行)
            name = cells[1] if len(cells) > 1 else ""
            if not name or re.search(r'^(序号|合计|股东名称|—)$', name): continue
            if '是否备案' in name: continue

            # 找编码(6位字母数字组合)
            code_m = re.search(r'([A-Z]{2,3}\d{3,6}|\d{5,6})', line)
            filing_code = code_m.group(1) if code_m else None

            # 找备案日期
            date_m = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', line)
            filing_date = f"{date_m.group(1)}-{int(date_m.group(2)):02d}-{int(date_m.group(3)):02d}" if date_m else None

            if filing_code:
                results.append({'fund_name': name, 'filing_code': filing_code, 'filing_date': filing_date})

    # 方法2: 从文本提取管理人
    manager_map = {}
    for m in re.finditer(
        r'([一-龥]{2,20}(?:创业投资|股权投资|创投).*?)的基金管理人([一-龥]{2,30}(?:有限责任公司|股份有限公司|管理有限公司|资产管理|投资管理[一-龥]{0,10}))'
        r'.*?登记编号为\s*(\w{6,14})', text
    ):
        fund_short = m.group(1).strip()
        manager = m.group(2).strip()
        mgr_code = m.group(3).strip()
        manager_map[fund_short] = {'manager': manager, 'manager_code': mgr_code}

    # 合并: 匹配基金→管理人
    for r in results:
        for key, val in manager_map.items():
            if key[:4] in r['fund_name'] or r['fund_name'][:4] in key:
                r['fund_manager'] = val['manager']
                r['manager_filing_code'] = val['manager_code']
                break

    return results


def classify(name):
    if re.search(r'(政府|引导|国有|国家|中小企业)', name): return '政府基金'
    if re.search(r'(天使|种子|孵化)', name): return 'VC'
    if re.match(r'^[A-Z]', name): return '外资基金'
    return 'PE'


def main():
    conn = pg8000.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("DELETE FROM zbq_pe_fund_detail")
    conn.commit()
    total = 0

    for code, (name, pdf_name, page) in PE_PAGES.items():
        pdf_path = PDF_DIR / pdf_name
        print(f"\n📄 {name}({code}) p{page}")
        funds = parse_pe_table(pdf_path, page)
        for f in funds:
            cur.execute("""
                INSERT INTO zbq_pe_fund_detail
                    (event_id, company_name, stock_code, fund_name, fund_type,
                     filing_code, filing_date, fund_manager, manager_filing_code,
                     pdf_page, evidence_text, confidence, review_status)
                VALUES (%s,%s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s,%s)
            """, (
                f"{code}_pf_{total:03d}", name, code,
                f['fund_name'][:200], classify(f['fund_name']),
                f['filing_code'], f.get('filing_date'),
                f.get('fund_manager'), f.get('manager_filing_code'),
                page,
                f"PE备案表p{page}提取: {f['fund_name']} {f['filing_code']}",
                0.8, 'extracted',
            ))
            total += 1
            mgr = f.get('fund_manager', '?')
            print(f"  ✅ {f['fund_name']}: {f['filing_code']} | 管理人: {mgr}")

    conn.commit()
    cur.execute("SELECT COUNT(*) FROM zbq_pe_fund_detail")
    print(f"\n总计: {cur.fetchone()[0]} 条PE基金记录")
    conn.close()


if __name__ == "__main__":
    main()
