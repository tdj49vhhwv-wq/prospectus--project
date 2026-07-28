"""
Week 6 Pydantic v2 模型 — PE/VC 专项提取

新增:
  - PEFundDetail: PE基金详情（备案编码、GP/LP结构、管理人信息）
  - event_id: 统一主键（{code}_{date}_{type}_{seq}）
  - processing_status: 状态机追踪（PENDING→EXTRACTED→...→VERIFIED）
  - 继承 Week3 的 SubscriptionFlow / ShareTransferFlow / EquitySnapshot
  - investor_type 字段：标识PE/VC/政府基金/产业资本/自然人
"""
import sys
from pathlib import Path
from typing import Optional, List
from enum import Enum
from datetime import date, datetime

# 复用 Week2 schema（公共模型定义）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "week2" / "schemas"))
try:
    from models import (
        SubscriptionFlow,
        ShareTransferFlow,
        EquitySnapshot,
        RecordType,
        EventContext,
        DataSource,
        PaymentMethod,
        ShareholderTypeDetail,
        TransferType,
    )
    HAS_WEEK3_SCHEMA = True
except ImportError:
    HAS_WEEK3_SCHEMA = False

from pydantic import BaseModel, Field, field_validator


# ============================================================
# 新增枚举
# ============================================================

class InvestorType(str, Enum):
    """投资人类型（PE/VC分类）"""
    PE = "PE"
    VC = "VC"
    GOVERNMENT_FUND = "政府基金"
    INDUSTRY_CAPITAL = "产业资本"
    BROKER_DIRECT = "券商直投"
    INDIVIDUAL = "自然人"
    OTHER = "其他"


class FundType(str, Enum):
    """基金类型"""
    PE_FUND = "PE基金"
    VC_FUND = "VC基金"
    GOVERNMENT_GUIDANCE = "政府引导基金"
    INDUSTRY_FUND = "产业基金"
    BUYOUT_FUND = "并购基金"
    ANGEL_FUND = "天使基金"
    OTHER = "其他"


class ProcessingStatus(str, Enum):
    """记录级处理状态机

    PENDING → EXTRACTED → SCHEMA_VALIDATED → CROSS_CHECKED → VERIFIED
       ↓                       ↓
    ERROR              MANUAL_REVIEW
    """
    PENDING = "PENDING"                   # 待提取
    EXTRACTED = "EXTRACTED"               # 已自动提取
    SCHEMA_VALIDATED = "SCHEMA_VALIDATED"  # Pydantic 校验通过
    CROSS_CHECKED = "CROSS_CHECKED"        # 数值交叉验证通过
    VERIFIED = "VERIFIED"                  # 人工确认通过（终态）
    MANUAL_REVIEW = "MANUAL_REVIEW"        # 需人工复核（阻塞态）
    ERROR = "ERROR"                        # 提取/校验失败


class TraceabilityLevel(str, Enum):
    """数据溯源级别"""
    PDF_DISCLOSED = "pdf_disclosed"    # PDF 逐字直接披露
    CALCULATED = "calculated"          # 从 PDF 数据计算得出
    INFERRED = "inferred"              # 基于上下文推断
    EXTERNAL_REQUIRED = "external_required"  # 需外部数据源


# ============================================================
# PE基金详情 — PEFundDetail
# ============================================================

class BaseRecord(BaseModel):
    """所有记录类型的基类：统一主键 + 状态追踪"""
    event_id: str = Field(
        ...,
        min_length=1,
        pattern=r'^\d{6}_\d{8}_(sf|es|pf|st)_\d{3}$',
        description="统一主键: {stock_code}_{prospectus_date}_{record_type_abbr}_{seq:03d}"
    )
    processing_status: ProcessingStatus = Field(
        default=ProcessingStatus.EXTRACTED,
        description="记录级处理状态"
    )
    status_detail: Optional[str] = Field(
        None,
        description="状态备注（失败原因 / 待复核说明）"
    )
    traceability: TraceabilityLevel = Field(
        default=TraceabilityLevel.PDF_DISCLOSED,
        description="数据溯源级别"
    )
    extracted_at: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        description="提取时间戳"
    )


class PEFundDetail(BaseRecord):
    """
    PE基金详情: 回答"这个PE基金是谁管的、什么结构、多大规模"

    每行 = 一个PE/VC基金的详细信息
    数据来源: 招股书股东穿透披露 + 私募基金备案信息
    """
    record_type: str = Field(
        default="pe_fund_detail",
        description="记录类型标识"
    )
    company_name: str = Field(
        ...,
        min_length=1,
        description="被投公司全称"
    )
    stock_code: str = Field(
        ...,
        min_length=1,
        pattern=r'^\d{6}$',
        description="股票代码（6位）"
    )

    # ── 来源定位 ──
    source_page: str = Field(
        ...,
        min_length=1,
        description="PDF 页码"
    )

    # ── 基金基本信息 ──
    fund_name: str = Field(
        ...,
        min_length=1,
        description="基金全称"
    )
    fund_type: Optional[FundType] = Field(
        None,
        description="基金类型（PE/VC/政府引导/产业/并购/天使）"
    )
    filing_code: Optional[str] = Field(
        None,
        description="中基协备案编码（如 SNG030）"
    )
    filing_date: Optional[str] = Field(
        None,
        description="备案日期（YYYY-MM-DD）"
    )
    fund_size: Optional[float] = Field(
        None, ge=0,
        description="基金规模（万元）"
    )

    # ── 管理人信息 ──
    fund_manager: Optional[str] = Field(
        None,
        min_length=1,
        description="基金管理人全称"
    )
    manager_filing_code: Optional[str] = Field(
        None,
        description="管理人备案编码（如 P1003586）"
    )

    # ── GP/LP 结构 ──
    gp_name: Optional[str] = Field(
        None,
        description="普通合伙人（GP）名称"
    )
    lp_names: Optional[List[dict]] = Field(
        None,
        description="有限合伙人（LP）列表 [{name, ratio}]"
    )

    # ── 与被投公司的关系 ──
    shareholding_ratio: Optional[str] = Field(
        None,
        description="持有被投公司股份比例（如 9.16%）"
    )
    shares_held: Optional[float] = Field(
        None, ge=0,
        description="持有被投公司股份数量（万股）"
    )

    # ── 证据 ──
    evidence_text: str = Field(
        ...,
        min_length=20,
        description="原文逐字摘录"
    )
    data_source: str = Field(
        default="pdf_disclosed",
        description="数据来源"
    )
    notes: Optional[str] = Field(
        None,
        description="备注"
    )

    @field_validator("filing_date")
    @classmethod
    def check_date(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        import re
        if not re.match(r'^\d{4}-\d{2}(-\d{2})?$', v):
            raise ValueError(f"日期格式错误: {v}")
        return v


# ============================================================
# 扩展 SubscriptionFlow（加 investor_type）
# ============================================================

class SubscriptionFlowV4(SubscriptionFlow if HAS_WEEK3_SCHEMA else BaseModel):
    """
    Week4 版认缴流量: 在 Week3 基础上新增 investor_type 字段
    """
    investor_type: Optional[InvestorType] = Field(
        None,
        description="投资人类型（PE/VC/政府基金/产业资本/自然人）"
    )


# ============================================================
# 扩展 EquitySnapshot（加 shareholder_type_detail）
# ============================================================

class EquitySnapshotV4(EquitySnapshot if HAS_WEEK3_SCHEMA else BaseModel):
    """
    Week4 版股权快照: 在 Week3 基础上新增 shareholder_type_detail 字段
    """
    shareholder_type_detail: Optional[InvestorType] = Field(
        None,
        description="股东类型细分（PE/VC/政府基金/产业资本/自然人）"
    )


# ============================================================
# Schema 校验函数
# ============================================================

def validate_jsonl(jsonl_path: Path, model_class) -> dict:
    """
    用 Pydantic 逐行校验 JSONL 文件

    返回: {pass: int, warn: int, fail: int, errors: list}
    """
    import json

    stats = {"pass": 0, "warn": 0, "fail": 0, "errors": []}

    if not jsonl_path.exists():
        stats["errors"].append(f"文件不存在: {jsonl_path}")
        return stats

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                model_class(**data)
                stats["pass"] += 1
            except Exception as e:
                stats["fail"] += 1
                stats["errors"].append({
                    "line": line_num,
                    "error": str(e)[:200],
                })

    return stats
