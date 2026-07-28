"""
Week 3 Pipeline 统一配置 — 所有路径相对于 week3/ 目录
不硬编码任何个人电脑绝对路径
"""
from pathlib import Path

# week3/pipeline/ → week3/
WEEK3_ROOT = Path(__file__).resolve().parent.parent

# 输入目录
MANUAL_GOLD_DIR = WEEK3_ROOT / "manual_gold"
DATA_DIR = WEEK3_ROOT / "data"
PROMPTS_DIR = WEEK3_ROOT / "prompts"

# 输出目录
OUTPUTS_DIR = WEEK3_ROOT / "outputs"
AUTO_JSONL_DIR = OUTPUTS_DIR / "auto_jsonl"
AUTO_EXCEL_DIR = OUTPUTS_DIR / "auto_excel"
LOGS_DIR = WEEK3_ROOT / "logs"
RAW_LLM_DIR = LOGS_DIR / "raw_llm_outputs"
EVALUATION_DIR = WEEK3_ROOT / "evaluation"

# 确保输出目录存在
for d in [AUTO_JSONL_DIR, AUTO_EXCEL_DIR, LOGS_DIR, RAW_LLM_DIR, EVALUATION_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# 上游依赖: PDF解析后的MD文件 (review/目录)
# 注意: review/目录仍在项目根目录,这是上游依赖
PROJECT_ROOT = WEEK3_ROOT.parent
REVIEW_DIR = PROJECT_ROOT / "review"

# Gold 文件路径
SF_GOLD = MANUAL_GOLD_DIR / "subscription_flow_gold.jsonl"
ST_GOLD = MANUAL_GOLD_DIR / "share_transfer_flow_gold.jsonl"
ES_GOLD = MANUAL_GOLD_DIR / "equity_snapshot_gold.jsonl"
CC_GOLD = MANUAL_GOLD_DIR / "cross_check_gold.jsonl"

# 输出文件路径
AUTO_SF_JSONL = AUTO_JSONL_DIR / "auto_subscription_flow.jsonl"
AUTO_ST_JSONL = AUTO_JSONL_DIR / "auto_share_transfer_flow.jsonl"
AUTO_ES_JSONL = AUTO_JSONL_DIR / "auto_equity_snapshot.jsonl"
SCHEMA_LOG = LOGS_DIR / "schema_validation_log.csv"
CROSS_CHECK_LOG = LOGS_DIR / "cross_check_summary.csv"
COMPARISON_XLSX = EVALUATION_DIR / "auto_vs_gold_comparison.xlsx"
COMPARISON_JSON = EVALUATION_DIR / "auto_vs_gold_summary.json"

# 8家目标公司
TARGET_COMPANIES = {
    "三联锻造": {"code": "001282", "full": "芜湖三联锻造股份有限公司"},
    "友升股份": {"code": "603418", "full": "上海友升铝业股份有限公司"},
    "黄山谷捷": {"code": "301581", "full": "黄山谷捷股份有限公司"},
    "云汉芯城": {"code": "301563", "full": "云汉芯城（上海）互联网科技股份有限公司"},
    "赛分科技": {"code": "688758", "full": "苏州赛分科技股份有限公司"},
    "影石创新": {"code": "688775", "full": "影石创新科技股份有限公司"},
    "三协电机": {"code": "920100", "full": "常州三协电机股份有限公司"},
    "星图测控": {"code": "920116", "full": "中科星图测控技术股份有限公司"},
}

# schema模块路径
SCHEMA_MODULE = PROJECT_ROOT / "schemas"
