"""
项目配置模块 - 统一管理所有路径和常量
所有路径均基于项目根目录，不硬编码绝对路径
"""
from pathlib import Path

# 项目根目录：config.py 的上上级目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 子目录
CODE_DIR = PROJECT_ROOT / "code"
REVIEW_DIR = PROJECT_ROOT / "review"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
LOG_DIR = PROJECT_ROOT / "logs"
DATA_DIR = PROJECT_ROOT / "data"
COMPANY_LISTS_DIR = PROJECT_ROOT / "company_lists"
SOURCE_NOTES_DIR = PROJECT_ROOT / "source_notes"
PRESENTATION_DIR = PROJECT_ROOT / "presentation"
PDF_DIR = PROJECT_ROOT / "data" / "prospectus_pdfs"

# 确保必要目录存在
LOG_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
REVIEW_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 融资历史相关关键词
FINANCING_KEYWORDS = [
    "发行人基本情况", "历史沿革", "股本演变", "历次增资",
    "股权转让", "股东变化", "股东情况", "公司设立", "发起人",
    "注册资本.*增加", "融资", "改制", "有限公司阶段", "股份公司阶段",
]

# JSON Schema 定义
REQUIRED_EVENT_FIELDS = [
    "event_order", "event_date", "date_type", "event_type",
    "disclosed_round", "inferred_round", "round_inference_basis",
    "total_investment_amount", "currency", "share_price",
    "pre_money_valuation", "post_money_valuation", "valuation_basis",
    "investors", "source_section", "source_page", "evidence_text", "confidence"
]

REQUIRED_INVESTOR_FIELDS = [
    "investor_original_name", "investor_short_name", "investor_type",
    "is_pevc", "investment_amount", "shares_acquired",
    "shareholding_ratio_after_event", "exit_status_before_ipo"
]

# 需要排除的公告类型关键词
EXCLUDE_KEYWORDS = [
    "提示性公告", "提示性", "上市公告书", "发行公告",
    "审核问询函", "问询回复", "问询函", "落实函",
    "审核中心意见", "反馈意见", "发行保荐书", "上市保荐书",
    "审计报告", "法律意见书", "律师工作报告",
    "附录", "附件", "摘要", "更正", "补充", "修改", "修订",
]
