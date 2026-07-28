"""
Pipeline 统一配置 — 所有路径相对于项目根目录
不硬编码任何个人电脑绝对路径
"""
from pathlib import Path

# scripts/ → 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 输入
MANUAL_GOLD_DIR = PROJECT_ROOT / "manual_gold"
DATA_DIR = PROJECT_ROOT / "data"
PROMPTS_DIR = PROJECT_ROOT / "prompts"
REVIEW_DIR = PROJECT_ROOT / "review"
SCHEMA_MODULE = PROJECT_ROOT / "schemas"

# 输出
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
AUTO_JSONL_DIR = OUTPUTS_DIR / "jsonl"
AUTO_EXCEL_DIR = OUTPUTS_DIR / "excel"
LOGS_DIR = PROJECT_ROOT / "logs"
RAW_LLM_DIR = LOGS_DIR / "raw_llm_outputs"
REPORTS_DIR = PROJECT_ROOT / "reports"

for d in [AUTO_JSONL_DIR, AUTO_EXCEL_DIR, LOGS_DIR, RAW_LLM_DIR, REPORTS_DIR, MANUAL_GOLD_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Gold 文件
SF_GOLD = MANUAL_GOLD_DIR / "subscription_flow_gold.jsonl"
ST_GOLD = MANUAL_GOLD_DIR / "share_transfer_flow_gold.jsonl"
ES_GOLD = MANUAL_GOLD_DIR / "equity_snapshot_gold.jsonl"
CC_GOLD = MANUAL_GOLD_DIR / "cross_check_gold.jsonl"

# Auto 输出
AUTO_SF_JSONL = AUTO_JSONL_DIR / "auto_subscription_flow.jsonl"
AUTO_ST_JSONL = AUTO_JSONL_DIR / "auto_share_transfer_flow.jsonl"
AUTO_ES_JSONL = AUTO_JSONL_DIR / "auto_equity_snapshot.jsonl"

# 日志
SCHEMA_LOG = LOGS_DIR / "schema_validation_log.csv"
CROSS_CHECK_LOG = LOGS_DIR / "cross_check_summary.csv"

# 对比
COMPARISON_XLSX = REPORTS_DIR / "auto_vs_gold_comparison.xlsx"
COMPARISON_JSON = REPORTS_DIR / "auto_vs_gold_summary.json"

# 8家目标
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
