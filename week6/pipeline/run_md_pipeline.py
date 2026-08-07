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
    # 增资：注册资本由X万元增至Y万元
    (r'(\d{4}\s*年\s*\d{1,2}\s*月).*?注册资本由\s*[\d,]+\.?\d*\s*万元增至\s*([\d,]+\.?\d*)\s*万元', '增资'),
    # 增资：第N次增资X万元，注册资本增至Y
    (r'(\d{4}\s*年\s*\d{1,2}\s*月).*?第[一二三四五六七八九十]+次增资\s*([\d,]+\.?\d*)\s*万元.*?注册资本[增至为]*\s*([\d,]+\.?\d*)\s*万元', '增资'),
    # 增资：增资至X万元
    (r'(\d{4}\s*年\s*\d{1,2}\s*月).*?增资至\s*([\d,]+\.?\d*)\s*万元', '增资'),
    # 增资：股本总额增至X万股
    (r'(\d{4}\s*年\s*\d{1,2}\s*月).*?股本总额增至\s*([\d,]+\.?\d*)\s*万股', '增资'),
    # 增资：增加注册资本X万元（允许注/册/资/本间换行）
    (r'(\d{4}\s*年\s*\d{1,2}\s*月).*?增加注\s*册\s*资\s*本\s*([\d,]+\.?\d*)\s*万元', '增资'),
    # 增资：认购（上述）新增股份X万股
    (r'(\d{4}\s*年\s*\d{1,2}\s*月).*?认购(?:上述)?新增股份\s*([\d,]+\.?\d*)\s*万股', '增资'),
    # 增资：增发股份X股
    (r'(\d{4}\s*年\s*\d{1,2}\s*月).*?增发股份\s*([\d,]+\.?\d*)\s*股', '增资'),
    # 增资：有限（公司）设立 + 注册资本（设立出资口径）
    (r'(\d{4}\s*年\s*\d{1,2}\s*月).*?(?:有限(?:公司)?|有限公司)设立.*?注册资本[为：:]?\s*([\d,]+\.?\d*)\s*万元', '增资'),
    # 增资：名称预先登记核准
    (r'(\d{4}\s*年\s*\d{1,2}\s*月).*?名称预先登记核准', '增资'),
    # 增资：认缴出资X万元
    (r'(\d{4}\s*年\s*\d{1,2}\s*月).*?认缴出资\s*([\d,]+\.?\d*)\s*万元', '增资'),
    # 复合事件：增资及股权转让
    (r'(\d{4}\s*年\s*\d{1,2}\s*月).*?(?:第[一二三四五六七八九十]+次增资.*?转让(?:予|给)|第[一二三四五六七八九十]+次股权转让及增资|增加注册资本暨.*?股权转让|增资和.*?股权转让|股权转让及增资|增资及股权转让)', '增资及股权转让'),
    # 整体变更：折合股本/股本总额（日期在前）
    (r'(\d{4}\s*年\s*\d{1,2}\s*月).*?整体变更.*?(?:股本总额|折合股本)\s*([\d,]+\.?\d*)\s*万股?', '整体变更'),
    # 整体变更：折股X股
    (r'(\d{4}\s*年\s*\d{1,2}\s*月).*?折股\s*([\d,]+\.?\d*)\s*股', '整体变更'),
    # 整体变更：办理完毕工商变更登记
    (r'(\d{4}\s*年\s*\d{1,2}\s*月).*?整体变更.*?办理完毕.*?工商变更登记', '整体变更'),
    # 整体变更：折合股本X万元 + 核准/备案登记日（日期在后）
    (r'折合股本\s*([\d,]+\.?\d*)\s*万元.*?(\d{4}\s*年\s*\d{1,2}\s*月(?:\s*\d{1,2}\s*日)?).*?(?:核准|备案登记|登记注册|领取)', '整体变更'),
    # 股权转让：零对价转让给
    (r'(\d{4}\s*年\s*\d{1,2}\s*月(?:\s*\d{1,2}\s*日)?)[^。；]{0,150}?将其所\s*持.*?股权以零对价.*?转\s*让\s*给\s*([\s一-龥A-Za-z]{2,40})', '股权转让'),
    # 股权转让：以人民币0元的价格转让给
    (r'(\d{4}\s*年\s*\d{1,2}\s*月(?:\s*\d{1,2}\s*日)?)[^。；]{0,150}?将其持\s*有\s*的.*?以人民币0\s*元的价格转\s*让\s*给\s*([\s一-龥A-Za-z]{2,40})', '股权转让'),
    # 股权转让：以X万元的对价向Y转让股本
    (r'(\d{4}\s*年\s*\d{1,2}\s*月(?:\s*\d{1,2}\s*日)?)[^。；]{0,70}?([\s一-龥A-Za-z]{2,40}?)\s*以([\d,]+\.?\d*)\s*万元(?:的对价)?向\s*([\s一-龥A-Za-z]{2,40}?)\s*转\s*让(?:股本|股权|股份)', '股权转让'),
    # 股权转让：X%股权转让予
    (r'(\d{4}\s*年\s*\d{1,2}\s*月(?:\s*\d{1,2}\s*日)?)[^。；]{0,150}?将其持\s*有\s*的.*?(\d+(?:\.\d+)?)%\s*股权.*?转\s*让\s*予\s*([\s一-龥]{2,20})', '股权转让'),
    # 增资：设立出资（有限/公司设立 + 注册资本）
    (r'(\d{4}\s*年\s*\d{1,2}\s*月(?:\s*\d{1,2}\s*日)?)[^。；]{0,150}?(?:出资)?设立[^。；]{0,60}?(?:有限|公司|股份)[^。；]{0,220}?注册资本[为：:]?\s*([\d,]+\.?\d*)\s*万元', '增资'),
]


def normalize_date(date_str):
    m = re.match(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', date_str)
    if m: return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.match(r'(\d{4})\s*年\s*(\d{1,2})\s*月', date_str)
    if m: return f"{m.group(1)}-{int(m.group(2)):02d}"
    m = re.match(r'(\d{4})-(\d{1,2})-(\d{1,2})', date_str)
    if m: return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return date_str.strip() if date_str else ''


REGISTRATION_KEYWORDS = (
    "工商变更登记", "变更登记", "换发", "核准", "登记手续", "工商登记",
    "备案", "取得", "营业执照",
)


def prefer_registration_date(text, fallback):
    """在给定窗口内优先取其后紧跟工商/换发/核准等登记动作的日期。"""
    best = None
    for m in re.finditer(r'(\d{4}\s*年\s*\d{1,2}\s*月(?:\s*\d{1,2}\s*日)?)', text):
        ctx = text[m.end():m.end() + 40]
        if any(kw in ctx for kw in REGISTRATION_KEYWORDS):
            best = m.group(1)
            break
    return normalize_date(best) if best else fallback


def is_proposal_date(text):
    """首段日期是否为批复/股东会/决议/协议等“提议型”日期。"""
    m0 = re.search(r'\d{4}\s*年\s*\d{1,2}\s*月(?:\s*\d{1,2}\s*日)?', text)
    if not m0:
        return False
    ctx = text[m0.end():m0.end() + 40]
    return any(kw in ctx for kw in ("批复", "股东会", "决议", "签署", "协议",
                                    "审计报告", "评估报告", "会计师", "董事会",
                                    "缴纳", "申请", "股东决定"))


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


BLOCKED_PHRASES_GLOBAL = (
    "瑞安市", "三连零部件", "深圳三协", "第一美亚", "补充协议",
    "员工股权激励方案", "个人所得税", "完税证明", "整体变更设立日期",
    "设立北京岚锋",
)
BLOCKED_PHRASES_A = ("净资产折股", "评估", "股份总数", "长期股权投资", "追溯评估", "整体变更")
BLOCKED_PHRASES_F = ("验资报告",)


def is_blocked_record(event_context: str, evidence_text: str) -> bool:
    """过滤明显非发行人主体/非目标事件（范围外历史、子公司、境外代持等）。"""
    text = evidence_text or ""
    if any(p in text for p in BLOCKED_PHRASES_GLOBAL):
        return True
    if "昆山谷捷" in text and "谷捷有限" not in text:
        return True
    if event_context == "增资" and any(p in text for p in BLOCKED_PHRASES_A):
        return True
    if event_context == "资本公积转增" and any(p in text for p in BLOCKED_PHRASES_F):
        return True
    return False


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

                # 工商/换发/核准日期优先（股权转让、整体变更、吸收合并、复合事件）
                if ev_type in ("股权转让", "整体变更", "吸收合并", "增资及股权转让", "增资"):
                    has_leading_date = re.search(r'\d{4}\s*年\s*\d{1,2}\s*月', m.group(0)) is not None
                    if not has_leading_date or is_proposal_date(m.group(0)):
                        window = text[max(0, m.start() - 150):min(len(text), m.end() + 800)]
                        date_str = prefer_registration_date(window, date_str)

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
                if ev_type == "股权转让":
                    # 股权转让只取“转让给/转让予/向…转让”后的受让方，避免把转出方和背景文本混入
                    tail = text[m.start():min(len(text), m.end() + 160)]
                    m_tr = re.search(r'转\s*让\s*(?:给|予)\s*([^。；]{2,200})', tail)
                    chunk = m_tr.group(1) if m_tr else ""
                    if not chunk:
                        m_xiang = re.search(r'向\s*([\s一-龥A-Za-z]{2,40}?)\s*转\s*让', tail)
                        chunk = m_xiang.group(1) if m_xiang else ""
                    chunk = chunk.replace('\n', '')
                    investors = stable_unique_names(
                        [n for n in re.findall(r'[一-龥A-Za-z]{2,40}(?:有限(?:责任)?公司|合伙企业|基金|创投|投资|集团|中心|管理)?', chunk)
                         if is_valid_investor_name(n)],
                        limit=10,
                    )
                else:
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
                    if is_blocked_record(ev_type, ctx):
                        continue
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
