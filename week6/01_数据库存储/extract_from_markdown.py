"""
从MinerU markdown补充提取股权快照 — 学习刘宇轩方法

PDF提取不到的图片表格页，改用MinerU markdown文本解析。
三协电机p30-32、星图测控p44-48等页面在PDF为图片格式，但MinerU已转为文本。
"""
import re, sys, os
from pathlib import Path
import pg8000

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'pipeline'))
from table_parser import find_shareholder_tables, parse_markdown_table

# DB_CONFIG → from pipeline.db_config import DB_CONFIG
import sys; sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'pipeline'))
try:
    from db_config import DB_CONFIG
except ImportError:
    DB_CONFIG = {
    'host': '<server-host>', 'port': 5433, 'database': 'student',
    'user': '<redacted>', 'password': os.environ.get('DB_PASSWORD', ''),
}

REVIEW_DIR = Path('/Users/zhaobingqing/GitHub/prospectus-pevc-project/week1/review')

# 8家公司 → MinerU markdown 文件映射
MD_FILES = {
    "920100": [  # 三协电机
        ("t0|深圳三协设立", "2025-07-11", 30, "三协电机_招股书_正式稿_20250711.md"),
    ],
    "920116": [  # 星图测控
        ("t0|报告期初", "2024-12-20", 44, "星图测控_招股书_正式稿_20241220.md"),
        ("t1|代持还原后", "2024-12-20", 46, "星图测控_招股书_正式稿_20241220.md"),
        ("t2|第一次增资后", "2024-12-20", 48, "星图测控_招股书_正式稿_20241220.md"),
    ],
    "001282": [  # 三联锻造（使用分段文件1/2/3合并）
        ("t0|报告期初", "2023-05-17", 36, "三联锻造1.md"),
        ("t1|第一次增资后", "2023-05-17", 37, "三联锻造2.md"),
    ],
    "688775": [  # 影石创新 p68缺失
        ("t1|2019年增资后", "2025-06-06", 68, "688775_影石创新_招股书_正式稿_20250606.md"),
    ],
}

NAME_MAP = {
    "920100": "三协电机", "920116": "星图测控", "001282": "三联锻造",
    "688775": "影石创新", "301563": "云汉芯城", "301581": "黄山谷捷",
    "603418": "友升股份", "688758": "赛分科技",
}


def classify(name):
    if not name or len(name) < 2: return '其他'
    if re.search(r'(政府|引导|国有|国家)', name): return '政府基金'
    if re.search(r'(有限|合伙|基金|创投|投资|中心|资本|达晨|高瓴|启明|IDG|深创投|东方富海|复星|国科|华泰|聚贝|金浦|杉|EARN|QM|CASREV)', name): return 'PE'
    if re.match(r'^[A-Z][A-Za-z0-9\s&]{2,30}$', name): return '外资基金'
    if re.match(r'^[一-龥]{2,4}$', name): return '自然人'
    return '其他'


def load_md_text(filename):
    """加载markdown文件内容（支持分段文件自动合并）"""
    path = REVIEW_DIR / filename
    if not path.exists():
        # 尝试分段文件
        base = filename.replace('.md', '')
        texts = []
        for i in range(1, 5):
            p = REVIEW_DIR / f"{base}{i}.md"
            if p.exists():
                texts.append(p.read_text(encoding='utf-8'))
        if texts:
            return '\n'.join(texts)
        return None
    return path.read_text(encoding='utf-8')


def extract_snapshot_from_md(md_text, target_page, label):
    """从markdown文本中提取指定页附近的股东表"""
    # MinerU markdown 使用 「## 第N页」 作为页码标记
    patterns = [
        rf'## 第{target_page}页',
        rf'第{target_page}页',
        rf'\- {target_page} \-',
    ]

    start = 0
    for pat in patterns:
        m = re.search(pat, md_text)
        if m:
            start = max(0, m.start() - 500)
            break

    if start == 0:
        print(f"    (未找到页码标记'第{target_page}页'，全文本搜索)")
        window = md_text[:10000]
    else:
        window = md_text[start:start + 5000]

    # 用table_parser解析表格
    tables = find_shareholder_tables(window)
    return tables


def main():
    conn = pg8000.connect(**DB_CONFIG)
    cur = conn.cursor()
    total = 0

    for code, snapshots in MD_FILES.items():
        name = NAME_MAP[code]

        for label, date, page, md_file in snapshots:
            print(f"\n📄 {name}({code}) {label} p{page} ← {md_file}")
            md_text = load_md_text(md_file)
            if not md_text:
                print(f"  ⚠ markdown文件不存在: {md_file}")
                continue

            tables = extract_snapshot_from_md(md_text, page, label)
            if not tables:
                print(f"  ⚠ 未找到股东表")
                continue

            # 取股东数最多的表
            best_table = max(tables, key=lambda t: t['count'])
            print(f"  ✅ 找到股东表: {best_table['count']} 名股东 (表头: {best_table['headers'][:4]})")

            for sh in best_table['shareholders']:
                cur.execute("""
                    INSERT INTO zbq_equity_snapshot
                        (event_id, company_name, stock_code, snapshot_label, snapshot_date,
                         shareholder_name, shares_wan, shareholding_pct, capital_wan,
                         shareholder_type, pdf_page,
                         evidence_text, extraction_notes, review_status)
                    VALUES (%s,%s,%s,%s,%s, %s,%s,%s,%s, %s,%s, %s,%s,%s)
                """, (
                    f"{code}_es_md_{total:04d}", name, code,
                    label[:50], date,
                    sh['name'], sh['shares'], sh['ratio'], sh['capital'],
                    classify(sh['name']), page,
                    f"MinerU markdown解析 p{page}: {sh['name']}",
                    f"学习刘宇轩方法：markdown→table_parser补充PDF图片页",
                    'extracted',
                ))
                total += 1

    conn.commit()
    cur.execute("SELECT COUNT(*) FROM zbq_equity_snapshot")
    print(f"\n{'='*60}")
    print(f"Markdown补充: {total} 条")
    print(f"zbq_equity_snapshot 总数: {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM ymx_equity_snapshot")
    print(f"ymx_equity_snapshot: {cur.fetchone()[0]}")
    conn.close()


if __name__ == "__main__":
    main()
