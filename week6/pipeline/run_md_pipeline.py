"""
从 Markdown 源跑完整 pipeline — 8家公司 subscription_flow 提取
"""
import sys, json, re, os
from pathlib import Path
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent))
from markdown_source import make_located_data

import pg8000
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', ''),
    'port': int(os.environ.get('DB_PORT', '5433')),
    'database': os.environ.get('DB_NAME', 'student'),
    'user': os.environ.get('DB_USER', ''),
    'password': os.environ.get('DB_PASSWORD', ''),
}

COMPANIES = [
    ("001282", "三联锻造"), ("301563", "云汉芯城"), ("301581", "黄山谷捷"),
    ("603418", "友升股份"), ("688758", "赛分科技"), ("688775", "影石创新"),
    ("920100", "三协电机"), ("920116", "星图测控"),
]

# 完整正则模式（Week7 成果）
PATTERNS = [
    # 定向发行
    (r'(?:(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)|(\d{4}\s*年\s*\d{1,2}\s*月)).*?'
     r'股票定向发行.*?发行价格[为：:]?\s*(\d+\.?\d*)\s*元/股.*?'
     r'发行普通股\s*(\d+[\d,]*\.?\d*)\s*万股.*?'
     r'募集资金总额[为：:]?\s*(\d+[\d,]*\.?\d*)\s*万元', '增资'),
    # 验收报告
    (r'截至\s*(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日).*?'
     r'已收到\s*(.+?)\s*缴纳的出资款\s*(\d+[\d,]*\.?\d*)\s*万元', '增资'),
    # 出资XX万
    (r'([一-龥]{2,30}(?:有限(?:责任)?公司|合伙企业|基金|创投|投资|集团|中心|管理)?)\s*'
     r'(?:以(?:货币|现金|实物|机器设备|土地使用权)方式)?出资\s*'
     r'([\d,]+\.?\d*)\s*万(?:元|美元)', '增资'),
    # 认购XX万股
    (r'([一-龥]{2,30}(?:有限(?:责任)?公司|合伙企业|基金|创投|投资|中心|管理)?)\s*'
     r'认购\s*([\d,]+\.?\d*)\s*万股?\s*[（(]\s*([\d,]+\.?\d*)\s*万元\s*[)）]', '增资'),
    # 认缴新增资本
    (r'([一-龥A-Za-z]{2,40}(?:有限(?:责任)?公司|合伙企业|基金|创投|投资|FUND)?)\s*'
     r'以(?:现金|货币)\s*([\d,]+\.?\d*)\s*万(?:元|美元)\s*认缴', '增资'),
    # 共同增资/增至
    (r'(\d{4}\s*年\s*\d{1,2}\s*月).*?(?:共同)?增资\s*([\d,]+\.?\d*)\s*万元.*?'
     r'注册资本[增至为]*\s*([\d,]+\.?\d*)\s*万元', '增资'),
    # 新增注册资本
    (r'(\d{4}\s*年\s*\d{1,2}\s*月).*?(?:新增|增加)注册资本\s*([\d,]+\.?\d*)\s*万(?:元|美元)', '增资'),
    # 整体变更折股
    (r'(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日).*?整体变更.*?折[成为合]\s*([\d,]+\.?\d*)\s*万股?', '整体变更'),
    # 设立：发行人基本信息表中的“有限公司成立日期”（限定发行人自身）
    (r'(?:有限公司)\s*成立日期\s*[:：]?\s*(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)', '设立'),
    # 设立：正文表述“公司/有限成立于”
    (r'(?:发行人|本公司|公司|有限|有限公司)成立于\s*[:：]?\s*(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)', '设立'),
    # 吸收合并
    (r'吸收合并\s*([一-龥]{2,30}(?:有限|公司)).*?注册资本.*?(?:变更为|增至)\s*([\d,]+\.?\d*)\s*万元', '吸收合并'),
    # 股权转让
    (r'([一-龥]{2,30}(?:有限(?:责任)?公司|合伙企业|基金|创投|投资)?)\s*将\s*([\d.]+)\s*万元.*?转让予\s*([一-龥]{2,30}(?:有限(?:责任)?公司|合伙企业|基金|创投|投资)?)', '股权转让'),
    # 转让予/转让给
    (r'([一-龥]{2,30})\s*(?:向|予|给)\s*([一-龥]{2,30}(?:有限(?:责任)?公司|合伙企业|基金|创投|投资)?)\s*转让.*?([\d,]+\.?\d*)\s*万(?:元|美元)', '股权转让'),
    # 资本公积转增
    (r'(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日).*?(?:资本公积|股票发行溢价).*?每\s*10\s*股\s*转增\s*(\d+\.?\d*)\s*股.*?转增\s*(\d+[\d,]*\.?\d*)\s*万股', '资本公积转增'),
    # 员工持股平台
    (r'([一-龥]+(?:合伙企业|管理中心|投资中心)[（(]有限合伙[)）])\s*(?:以货币方式)?(?:认缴)?出资\s*([\d,]+\.?\d*)\s*万元', '员工持股平台出资'),
]


def normalize_date(date_str):
    m = re.match(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', date_str)
    if m: return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.match(r'(\d{4})\s*年\s*(\d{1,2})\s*月', date_str)
    if m: return f"{m.group(1)}-{int(m.group(2)):02d}"
    m = re.match(r'(\d{4})-(\d{1,2})-(\d{1,2})', date_str)
    if m: return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return date_str.strip() if date_str else ''


def classify(name):
    if not name or len(name) < 2: return '其他'
    if re.search(r'(政府|引导|国有|国家)', name): return '政府基金'
    if re.search(r'(有限|合伙|基金|创投|投资|中心|资本|达晨|高瓴|启明|IDG|深创投|东方富海|复星|国科|华泰|聚贝|金浦|杉|EARN|QM|CASREV)', name): return 'PE'
    if re.match(r'^[A-Z][A-Za-z0-9\s&]{2,30}$', name): return '外资基金'
    if re.match(r'^[一-龥]{2,4}$', name): return '自然人'
    return '其他'


def stable_unique_names(names, limit=None):
    """Return cleaned unique names in deterministic Unicode sort order."""
    unique_names = sorted({name.strip() for name in names if len(name.strip()) >= 2})
    return unique_names if limit is None else unique_names[:limit]


NON_INVESTOR_TOKENS = (
    "法定代表人", "注册地址", "经营范围", "执行事务合伙人", "注册资本", "实收资本",
    "出资额", "出资比例", "成立日期", "注销日期", "统一社会信用代码", "企业类型",
    "主要生产经营地", "办公地址", "负责人", "营业执照", "证券代码", "股份总数",
    "招股说明书", "审计报告", "验资报告", "董事会", "股东会", "本次", "上述", "合计",
    "总计", "截至", "序号", "股东名称", "股权比例", "募集资金", "发行价格", "每股",
    "单位", "小计", "发行新股", "送股", "转增", "发行", "以及", "备注", "新增股东",
    "万元", "万股", "元/股", "元/注册资本", "出资", "认缴", "成立", "日期",
    "有限公司成立日期", "股份公司成立日期", "股份公司设立日期", "整体变更设立日期",
    "企业名称", "公司名称", "发行人名称", "住所", "邮政编码",
)


def is_valid_investor_name(name: str) -> bool:
    """过滤明显非投资人实体名。"""
    if not name or len(name.strip()) < 2:
        return False
    if re.fullmatch(r"[\d\s,.\-%/]+", name):
        return False
    if any(tok in name for tok in NON_INVESTOR_TOKENS):
        return False
    if name in ("公司", "有限", "发行人", "本公司", "（待识别）"):
        return False
    return True


def extract_from_snippets(snippets, company_code, company_name):
    """从文本片段提取订阅事件"""
    records = []
    seen = set()

    for snippet in snippets:
        text = snippet['text']
        page = snippet['pdf_page']

        for pattern, ev_type in PATTERNS:
            for m in re.finditer(pattern, text, re.DOTALL):
                groups = m.groups()

                # 提取日期
                date_str = ''
                for g in groups:
                    if g and re.search(r'\d{4}\s*年', str(g)):
                        date_str = normalize_date(g)
                        break

                # 提取数字
                nums = []
                for g in groups:
                    if not g: continue
                    if re.search(r'[年月日]', str(g)): continue
                    val = str(g).replace(',', '').strip()
                    if re.match(r'^[\d.]+$', val):
                        try: nums.append(float(val))
                        except: pass

                amount = nums[0] if nums else None
                shares = nums[1] if len(nums) > 1 else None
                price = nums[2] if len(nums) > 2 else None

                # 提取投资人
                investors = re.findall(
                    r'([一-龥A-Za-z]{2,30}(?:有限(?:责任)?公司|合伙企业|基金|创投|投资|集团|中心|管理|FUND)?)',
                    text[m.start():min(m.end()+300, len(text))]
                )
                # 过滤非投资人（明显非实体 + 非发行人主体）
                investors = stable_unique_names(
                    [i for i in investors if is_valid_investor_name(i)],
                    limit=8,
                )

                if not investors:
                    investors = ['（待识别）']

                ctx = text[max(0,m.start()-20):min(len(text),m.end()+100)].replace('\n',' ')[:300]

                for inv in investors:
                    key = (date_str, inv, ev_type)
                    if key in seen: continue
                    seen.add(key)

                    validated = bool(date_str) and inv != "（待识别）"

                    records.append({
                        "event_id": f"{company_code}_{date_str.replace('-','')}_{ev_type}_{len(records):03d}",
                        "company_name": company_name,
                        "stock_code": company_code,
                        "subscription_date": date_str,
                        "subscriber_name": inv[:200],
                        "shares_subscribed": shares,
                        "amount_subscribed": amount,
                        "price_per_share": price,
                        "event_context": ev_type,
                        "investor_type": classify(inv),
                        "source_page": f"MD p{page}",
                        "evidence_text": ctx[:500],
                        "data_source": "markdown_extracted",
                        "extraction_method": "regex_from_md",
                        "processing_status": "extracted",
                        "validation_status": "validated" if validated else "candidate",
                        "confidence": "high" if validated else "low",
                        "extracted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    })

    return records


def main():
    all_results = {}
    all_candidates = {}
    all_validated = {}

    for code, name in COMPANIES:
        print(f"\n{'='*50}")
        print(f"📄 {name} ({code})")
        located = make_located_data(code, name)
        if not located:
            print(f"  ⚠ markdown不可用，跳过")
            continue

        snippets = located['pevc_snippets']
        print(f"  {len(snippets)} 个文本段落")

        records = extract_from_snippets(snippets, code, name)

        # 确定性去重：同 (日期, 类型, 投资人, 金额, 股数) 只保留首条
        dedup_seen = set()
        deduped = []
        for r in records:
            dk = (r["subscription_date"], r["event_context"], r["subscriber_name"],
                  r["amount_subscribed"], r["shares_subscribed"])
            if dk in dedup_seen:
                continue
            dedup_seen.add(dk)
            deduped.append(r)
        records = sorted(deduped, key=lambda r: (r["subscription_date"], r["event_context"],
                                                 r["subscriber_name"]))

        candidates = [r for r in records if r["validation_status"] == "candidate"]
        validated = [r for r in records if r["validation_status"] == "validated"]
        print(f"  ✅ 候选 {len(records)} 条 / validated {len(validated)} 条")

        # 按类型统计
        from collections import Counter
        types = Counter(r['event_context'] for r in records)
        for t, c in types.most_common():
            print(f"    {t}: {c}")

        all_results[code] = records
        all_candidates[code] = records
        all_validated[code] = validated

    # 写 JSONL（candidate 与 validated 分目录）+ 入库（仅 validated）
    output_dir = Path('auto_output_md')
    output_dir.mkdir(exist_ok=True)
    candidate_dir = output_dir / "candidate"
    validated_dir = output_dir / "validated"
    candidate_dir.mkdir(exist_ok=True)
    validated_dir.mkdir(exist_ok=True)

    grand_total = 0
    validated_total = 0
    for code, records in all_results.items():
        candidate_path = candidate_dir / f"{code}_subscription_flow.jsonl"
        with open(candidate_path, 'w', encoding='utf-8') as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
        validated_path = validated_dir / f"{code}_subscription_flow.jsonl"
        with open(validated_path, 'w', encoding='utf-8') as f:
            for r in all_validated[code]:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
        grand_total += len(records)
        validated_total += len(all_validated[code])

    # 尝试入库
    try:
        conn = pg8000.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("DELETE FROM zbq_subscription_flow WHERE extraction_method = 'regex_from_md'")
        inserted = 0
        for records in all_validated.values():
            for r in records:
                try:
                    cur.execute("""
                        INSERT INTO zbq_subscription_flow
                            (event_id, company_name, stock_code, event_type, event_date,
                             investor_name, investor_type,
                             subscription_qty_wan, subscription_amount_wan, subscription_price,
                             pdf_page, evidence_text, extraction_method, review_status)
                        VALUES (%s,%s,%s,%s,%s, %s,%s, %s,%s,%s, %s,%s,%s,%s)
                    """, (
                        r['event_id'], r['company_name'], r['stock_code'],
                        r['event_context'], r['subscription_date'],
                        r['subscriber_name'], r['investor_type'],
                        r['shares_subscribed'], r['amount_subscribed'], r['price_per_share'],
                        _parse_page(r['source_page']), r['evidence_text'],
                        'regex_from_md', 'extracted',
                    ))
                    inserted += 1
                except Exception as e:
                    pass
        conn.commit()
        cur.execute("SELECT COUNT(*) FROM zbq_subscription_flow WHERE extraction_method='regex_from_md'")
        db_count = cur.fetchone()[0]
        conn.close()
        print(f"\n入库: {db_count} 条")
    except Exception as e:
        print(f"\n入库跳过(数据库不可用): {e}")

    print(f"\n{'='*50}")
    print(f"总计: 候选 {grand_total} 条 / validated {validated_total} 条")
    print(f"输出: {output_dir}/candidate/ 与 {output_dir}/validated/")
    return grand_total


def _parse_page(val):
    if not val: return None
    m = re.search(r'p(\d+)', str(val))
    return int(m.group(1)) if m else None


if __name__ == "__main__":
    main()
