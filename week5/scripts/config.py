"""
Week 4 Pipeline 统一配置
- 定位与抽取完全分离（两步独立）
- 所有路径相对 week4/ 目录，不硬编码绝对路径
- 支持 PyMuPDF 表格提取 + PaddleOCR 备选
"""
from pathlib import Path

# week4/scripts/ → week4/
WEEK4_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = WEEK4_ROOT.parent

# ── 输入 ──
PDF_DIR = PROJECT_ROOT / "week1" / "data" / "week1PDF"
REVIEW_DIR = PROJECT_ROOT / "review"
MANUAL_GOLD_DIR = WEEK4_ROOT / "manual_gold"

# ── 输出 ──
OUTPUTS_DIR = WEEK4_ROOT / "outputs"
JSONL_DIR = OUTPUTS_DIR / "jsonl"
EXCEL_DIR = OUTPUTS_DIR / "excel"
LOGS_DIR = WEEK4_ROOT / "logs"
PROMPTS_DIR = WEEK4_ROOT / "prompts"
SCHEMAS_DIR = WEEK4_ROOT / "schemas"

for d in [OUTPUTS_DIR, JSONL_DIR, EXCEL_DIR, LOGS_DIR, PROMPTS_DIR, SCHEMAS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── 输出文件路径 ──
STEP_LOG = LOGS_DIR / "step_log.csv"
SF_JSONL = JSONL_DIR / "subscription_flow.jsonl"
ST_JSONL = JSONL_DIR / "share_transfer_flow.jsonl"
ES_JSONL = JSONL_DIR / "equity_snapshot.jsonl"
PE_DETAIL_JSONL = JSONL_DIR / "pe_fund_detail.jsonl"
SCHEMA_LOG = LOGS_DIR / "schema_validation_log.csv"
CROSS_CHECK_LOG = LOGS_DIR / "cross_check_summary.csv"

# ── Week4 目标公司：三协电机（聚焦PE/VC章节） ──
TARGET = {
    "name": "三协电机",
    "code": "920100",
    "full_name": "常州三协电机股份有限公司",
    "pdf": "三协电机_招股书_正式稿_20250711.pdf",
    "md": "三协电机_招股书_正式稿_20250711.md",
}

# ── PE/VC 章节定位关键词（两级：章节级 + 段落级） ──
SECTION_KEYWORDS = {
    # 一级：章节标题定位
    "chapter": [
        "发行人基本情况",
        "发行融资情况",
        "股权结构",
        "股东及实际控制人",
        "历史沿革",
        "股本演变",
    ],
    # 二级：PE/VC 相关内容定位
    "pevc_content": [
        "创业投资",
        "私募基金",
        "定向发行",
        "增资",
        "股权转让",
        "股票发行",
        "基金备案",
        "基金管理人",
        "普通合伙人",
        "有限合伙人",
    ],
}

# ── PE/VC 投资人类型枚举 ──
INVESTOR_TYPE_KEYWORDS = {
    "PE": ["创业投资", "股权投资", "私募基金", "创投", "并购基金"],
    "VC": ["天使投资", "风险投资", "种子", "孵化"],
    "政府基金": ["政府引导基金", "产业基金", "国有资本", "国家集成电路"],
    "产业资本": ["产业投资", "战略投资", "产业资本"],
    "券商直投": ["证券.*投资", "券商直投"],
    "自然人": ["自然人"],
}

# ── 排除词（不是投资人的实体） ──
EXCLUDE_ENTITIES = [
    "会计师事务所", "律师事务所", "评估师事务所",
    "保荐机构", "主承销商", "审计机构",
    "发行人", "本公司", "公司自身",
]

# ── event_id 规范 ──
# 格式: {stock_code}_{prospectus_date}_{record_type}_{seq:03d}
# record_type 缩写: sf=subscription_flow, es=equity_snapshot,
#                   pf=pe_fund_detail, st=share_transfer_flow
# 例: 920100_20250711_sf_001
RECORD_TYPE_ABBR = {
    "subscription_flow": "sf",
    "equity_snapshot": "es",
    "pe_fund_detail": "pf",
    "share_transfer_flow": "st",
}

# ── processing_status 状态机 ──
# PENDING → EXTRACTED → SCHEMA_VALIDATED → CROSS_CHECKED → VERIFIED
#    ↓                       ↓
# ERROR              MANUAL_REVIEW (需人工确认)
STATUS_TRANSITIONS = {
    "PENDING": ["EXTRACTED", "ERROR"],
    "EXTRACTED": ["SCHEMA_VALIDATED", "MANUAL_REVIEW", "ERROR"],
    "SCHEMA_VALIDATED": ["CROSS_CHECKED", "MANUAL_REVIEW", "ERROR"],
    "CROSS_CHECKED": ["VERIFIED", "MANUAL_REVIEW"],
    "VERIFIED": [],                # 终态
    "MANUAL_REVIEW": ["EXTRACTED", "VERIFIED", "ERROR"],  # 人工修正后回流
    "ERROR": ["PENDING"],          # 修复后重新开始
}

# ── 数据溯源链（显式声明） ──
# PDF页码 → raw_text(PyMuPDF/MinerU逐字提取) → evidence_text(原文摘录) → structured_field
# 三者必须可交叉验证:
#   1. source_page: PDF 页码，可回 PDF 定位
#   2. evidence_text: PDF 原文逐字摘录，不可概括
#   3. structured_field: 从 evidence_text 提取的结构化值
# 规则:
#   - evidence_text 不包含的字段 → data_source="calculated"，不得标"pdf_disclosed"
#   - evidence_text 有但 PDF 无法直接确认 → data_source="inferred"
#   - evidence_text 与 PDF 原文一致 → data_source="pdf_disclosed"
TRACEABILITY_CHAIN = """
PDF页码 (source_page)
  └─ raw_text (MinerU/PyMuPDF 逐字提取)
       └─ evidence_text (原文摘录, 逐字不概括)
            └─ structured_field (amount, shares, ratio, name...)
"""


# ── JSON配置驱动的通用提取规则（从extract_json_config.py合并）──
# 一套配置, 跨公司复用。换公司只需改TARGET, 不改提取逻辑
GENERIC_EXTRACTION_RULES = {
  "增资_标准发行": {
    "anchors": [
      "发行价格",
      "发行普通股",
      "募集资金",
      "增资价格",
      "认购价格",
      "定向发行",
      "股票发行",
      "增资.*元/股"
    ],
    "extract": {
      "price": "(?:发行价格|增资价格|认购价格)[为：:]?\\s*([\\d.]+)\\s*元",
      "shares": "(?:发行普通股|增发.*?股|新增.*?股|认购)\\s*([\\d,]+\\.?\\d*)\\s*万股",
      "amount": "(?:募集资金总额|增资.*?金额|认购金额)[为：:]?\\s*([\\d,]+\\.?\\d*)\\s*万元",
      "date": "(\\d{4}\\s*年\\s*\\d{1,2}\\s*月\\s*\\d{1,2}\\s*日)"
    }
  },
  "增资_验资报告": {
    "anchors": [
      "已收到",
      "缴纳的出资款",
      "验资报告",
      "经审验",
      "出资款"
    ],
    "extract": {
      "investors_raw": "已收到\\s*(.+?)\\s*(?:等?\\d+名.*?认购|缴纳的出资款)",
      "amount": "出资款\\s*([\\d,]+\\.?\\d*)\\s*万元",
      "date": "截至\\s*(\\d{4}\\s*年\\s*\\d{1,2}\\s*月\\s*\\d{1,2}\\s*日)"
    }
  },
  "资本公积转增": {
    "anchors": [
      "资本公积",
      "转增",
      "每10股",
      "权益分派"
    ],
    "extract": {
      "ratio": "每\\s*10\\s*股\\s*转增\\s*([\\d.]+)\\s*股",
      "shares": "转增\\s*([\\d,]+\\.?\\d*)\\s*万股",
      "date": "(\\d{4}\\s*年\\s*\\d{1,2}\\s*月\\s*\\d{1,2}\\s*日)"
    }
  },
  "设立": {
    "anchors": [
      "成立日期",
      "成立于",
      "设立",
      "注册资本"
    ],
    "extract": {
      "date": "(?:成立日期|成立于)\\s*[:：]?\\s*(\\d{4}\\s*年\\s*\\d{1,2}\\s*月\\s*\\d{1,2}\\s*日)",
      "registered_capital": "注册资本\\s*[:：]?\\s*([\\d,]+\\.?\\d*)\\s*万"
    }
  },
  "股改": {
    "anchors": [
      "整体变更",
      "折股",
      "股份公司",
      "股份有限公司"
    ],
    "extract": {
      "net_assets": "净资产[总计为]?\\s*([\\d,]+\\.?\\d*)\\s*[万元]",
      "shares": "折[为合].*?([\\d,]+\\.?\\d*)\\s*万股",
      "ratio_raw": "按?\\s*([\\d.]+)\\s*[:：]\\s*([\\d.]+)\\s*[的]?比例折股",
      "date": "(\\d{4}\\s*年\\s*\\d{1,2}\\s*月\\s*\\d{1,2}\\s*日).*?(?:核准|登记|注册|营业执照)"
    }
  },
  "股权转让": {
    "anchors": [
      "股权转让",
      "转让.*股权",
      "代持.*解除",
      "代持.*还原"
    ],
    "extract": {
      "transferor": "([一-龥]{2,20}(?:有限|合伙|企业|公司|投资|中心)?)\\s*(?:将其所持|将其持有的)",
      "transferee": "(?:转让给|转让予)\\s*([一-龥]{2,20}(?:有限|合伙|企业|公司|投资|中心)?)",
      "date": "(\\d{4}\\s*年\\s*\\d{1,2}\\s*月\\s*\\d{1,2}\\s*日)"
    }
  },
  "PE备案": {
    "anchors": [
      "备案编码",
      "私募基金",
      "基金管理人",
      "SNG",
      "SVU",
      "P10"
    ],
    "extract": {
      "filing_code": "备案编码[为：:]?\\s*(\\w{6})",
      "fund_name": "([一-龥]{2,20}(?:创业投资|创投|股权投资)[一-龥]{0,20}(?:企业|基金|合伙))",
      "manager": "基金管理人[为：:]?\\s*([一-龥]{2,30}(?:有限(?:责任)?公司|管理有限公司|资产管理))"
    }
  }
}
