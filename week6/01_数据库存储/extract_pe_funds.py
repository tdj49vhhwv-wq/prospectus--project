"""
P1: PE基金详情扩展 — 从PDF逐公司提取私募基金备案信息

招股书中PE基金信息通常在:
- "发行人基本情况" → "持有5%以上股份的股东"
- 包含: 基金全称、备案编码、管理人、GP、LP、出资比例
"""
import re, os, json
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

# 已知PE基金对应的PDF页码（从final事件总表和ymx数据推断）
PE_TARGETS = [
    # 三协电机 (done)
    # 黄山谷捷
    ("301581", "黄山谷捷", "黄山谷捷_招股书_正式稿_20241219.pdf",
     [("赛格高技术", 60), ("上汽科技/SAIC", 64)]),
    # 云汉芯城
    ("301563", "云汉芯城", "云汉芯城_招股书_正式稿_20250925.pdf",
     [("深创投", 58), ("东方富海", 56), ("国科瑞华", 57), ("CASREV FUND", 57)]),
    # 赛分科技 — 最多PE
    ("688758", "赛分科技", "赛分科技_招股书_正式稿_20250106.pdf",
     [("高瓴祈睿", 59), ("国寿疌泉", 59), ("复星惟盈", 286), ("源峰磐赛", 59),
      ("国药中生", 59), ("夏尔巴二期", 59), ("华泰大健康一号", 301), ("聚贝投资", 60)]),
    # 友升股份 — 达晨系
    ("603418", "友升股份", "友升股份_招股书_正式稿_20250918.pdf",
     [("达晨创联", 96), ("金浦临港", 44), ("金浦科创", 44), ("杉晖", 80)]),
    # 影石创新 — 外资
    ("688775", "影石创新", "影石创新_招股书_正式稿_20250606.pdf",
     [("EARN ACE", 85), ("QM101", 81), ("IDG", 81), ("香港迅雷", 85), ("苏宁", 85)]),
    # 三联锻造
    ("001282", "三联锻造", "三联锻造_招股书_正式稿_20230517.pdf",
     [("高新同华", 33)]),
    # 星图测控
    ("920116", "星图测控", "星图测控_招股书_正式稿_20241220.pdf",
     [("策星九天", 44), ("幸福一期", 44), ("幸福二期", 62)]),
]


def extract_pe_info(pdf_path, fund_name, page):
    """从PDF指定页提取PE基金信息"""
    with pdfplumber.open(str(pdf_path)) as pdf:
        if page > len(pdf.pages): return {}
        text = pdf.pages[page - 1].extract_text() or ""

    info = {'fund_name': fund_name, 'page': page}

    # 备案编码
    fm = re.search(r'(?:备案编码|基金编号)[为：:]\s*(\w{6,12})', text)
    if fm: info['filing_code'] = fm.group(1)

    # 管理人
    mm = re.search(r'(?:基金管理人|管理人)[为：:]\s*([一-龥]{2,30}(?:有限(?:责任)?公司|管理有限公司|资产管理|投资管理[一-龥]{0,10}))', text)
    if mm: info['fund_manager'] = mm.group(1)

    # GP
    gp = re.search(r'(?:执行事务合伙人|普通合伙人)[为：:]\s*([一-龥]{2,30}(?:有限(?:责任)?公司|管理有限公司|资产管理[一-龥]{0,10}))', text)
    if gp: info['gp_name'] = gp.group(1)

    # 备案日期
    dm = re.search(r'(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日).*?备案', text)
    if dm: info['filing_date'] = dm.group(1)

    return info


def classify_fund(name):
    if re.search(r'(政府|引导|国有|国家|中小企业)', name): return '政府基金'
    if re.search(r'(天使|种子|孵化)', name): return 'VC'
    if re.match(r'^[A-Z].*(?:FUND|Ltd|Limited|Capital)', name, re.IGNORECASE): return '外资基金'
    return 'PE'


def main():
    conn = pg8000.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("DELETE FROM zbq_pe_fund_detail")
    conn.commit()
    total = 0

    for code, name, pdf_name, funds in PE_TARGETS:
        pdf_path = PDF_DIR / pdf_name
        if not pdf_path.exists():
            print(f"  SKIP {code}: PDF不存在")
            continue

        print(f"\n📄 {name}({code})")
        for fund_name, page in funds:
            info = extract_pe_info(pdf_path, fund_name, page)
            if not info.get('filing_code'):
                print(f"  ⚠ {fund_name} p{page}: 未找到备案信息")
                continue

            cur.execute("""
                INSERT INTO zbq_pe_fund_detail
                    (event_id, company_name, stock_code, fund_name, fund_type,
                     filing_code, filing_date, fund_manager,
                     gp_name, pdf_page, evidence_text, confidence, review_status)
                VALUES (%s,%s,%s,%s,%s, %s,%s,%s, %s,%s,%s,%s,%s)
            """, (
                f"{code}_pf_{total:03d}", name, code,
                fund_name, classify_fund(fund_name),
                info['filing_code'], info.get('filing_date'),
                info.get('fund_manager'), info.get('gp_name'),
                page,
                f"提取自p{page}: {json.dumps(info, ensure_ascii=False)}",
                0.7, 'extracted',
            ))
            total += 1
            print(f"  ✅ {fund_name}: {info['filing_code']} | {info.get('fund_manager','?')}")

    conn.commit()
    cur.execute("SELECT COUNT(*) FROM zbq_pe_fund_detail")
    print(f"\n总计: {cur.fetchone()[0]} 条PE基金记录")
    conn.close()


if __name__ == "__main__":
    main()
