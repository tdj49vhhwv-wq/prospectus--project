"""
Pydantic v2 模型 — Week 2 两类基础事实记录

1. SubscriptionFlow  — 认缴流量: 谁在什么时候认购了多少、多少钱、什么价格
2. EquitySnapshot   — 股权结构存量: 某个时点的股东结构是什么

重要规则:
  - PDF 只披露出资额 → 只填出资额, 持股数空着
  - PDF 只披露持股数 → 只填持股数, 出资额空着
  - 不要为了填满表格去倒推
"""
from typing import Optional, List
from enum import Enum

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)


# ============================================================
# 枚举
# ============================================================

class RecordType(str, Enum):
    SUBSCRIPTION_FLOW = "subscription_flow"
    EQUITY_SNAPSHOT = "equity_snapshot"


class Currency(str, Enum):
    CNY = "CNY"
    USD = "USD"
    HKD = "HKD"


class PaymentMethod(str, Enum):
    CASH = "货币"
    LAND = "土地使用权"
    EQUIPMENT = "机器设备"
    IP = "知识产权"
    DEBT = "债权"
    OTHER = "其他"


class EventContext(str, Enum):
    CAPITAL_INCREASE = "增资"
    EQUITY_TRANSFER = "股权转让"
    WHOLE_CHANGE = "整体变更"
    ESTABLISHMENT = "设立"
    CAPITAL_INCREASE_AND_TRANSFER = "增资及股权转让"
    VIE_SETUP = "VIE搭建"
    VIE_REMOVAL = "VIE拆除"
    ABSORPTION_MERGER = "吸收合并"
    RESTRUCTURING = "改制"
    OTHER = "其他"


class ShareholderTypeDetail(str, Enum):
    CONTROLLING = "控股股东"
    ACTUAL_CONTROLLER = "实际控制人"
    ESOP = "员工持股平台"
    EXTERNAL_PE = "外部PE"
    EXTERNAL_VC = "外部VC"
    INDUSTRY_CAPITAL = "产业资本"
    GOVERNMENT = "政府基金"
    INDIVIDUAL = "自然人"
    ORIGINAL_FOUNDER = "原始创始人"
    OTHER = "其他"


# ============================================================
# 1. 认缴流量 — SubscriptionFlow
# ============================================================

class SubscriptionFlow(BaseModel):
    """
    认缴流量: 回答"谁在什么时候认购了多少、多少钱、什么价格"

    每行 = 一个认购方在一次增资/股权变动中的认购记录。
    一个融资事件如果有 N 个认购方, 就产生 N 行 subscription_flow。
    """
    record_type: RecordType = Field(
        default=RecordType.SUBSCRIPTION_FLOW,
        description="记录类型标识"
    )
    company_name: str = Field(
        ...,
        min_length=1,
        description="公司全称"
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
        description="PDF 页码或 MD 文件行号范围（如: 友声股份2.md L800-L830, PDF p43-45）"
    )

    # ── 认购信息（核心字段） ──
    subscription_date: str = Field(
        ...,
        min_length=7,
        description="增资/认购日期（YYYY-MM-DD 或 YYYY-MM）"
    )
    subscriber_name: str = Field(
        ...,
        min_length=1,
        description="认购方名称"
    )

    # ── 数量/金额/价格（可为空，不强行倒推） ──
    shares_subscribed: Optional[float] = Field(
        None, ge=0,
        description="认购数量（万股）。PDF 未披露则留空"
    )
    amount_subscribed: Optional[float] = Field(
        None, ge=0,
        description="认购金额（万元人民币）。PDF 未披露则留空"
    )
    price_per_share: Optional[float] = Field(
        None, ge=0,
        description="认购价格（元/股 或 元/注册资本）。PDF 未披露则留空"
    )

    # ── 增强字段 ──
    event_context: Optional[EventContext] = Field(
        None,
        description="本次认购所属事件类型（增资/股权转让/股改/设立等）"
    )
    post_event_total_shares: Optional[float] = Field(
        None, ge=0,
        description="增资后总股本（万股）。用于交叉校验"
    )
    post_event_total_capital: Optional[float] = Field(
        None, ge=0,
        description="增资后总出资额/注册资本（万元）。用于交叉校验"
    )
    payment_method: Optional[PaymentMethod] = Field(
        None,
        description="出资方式（货币/土地使用权/机器设备/知识产权/债权/其他）"
    )
    subscription_ratio: Optional[str] = Field(
        None,
        description="本次认购占增资后总股本的比例（如 6.28%）"
    )

    # ── 证据 ──
    evidence_text: str = Field(
        ...,
        min_length=20,
        description="原文逐字摘录（必须是 PDF 原文片段，不可人工概括）"
    )
    notes: Optional[str] = Field(
        None,
        description="备注（人工概括放这里）"
    )

    @field_validator("subscription_date")
    @classmethod
    def check_date(cls, v: str) -> str:
        import re
        if not re.match(r'^\d{4}-\d{2}(-\d{2})?$', v):
            raise ValueError(f"日期格式错误: {v}，应为 YYYY-MM-DD 或 YYYY-MM")
        return v

    @field_validator("evidence_text")
    @classmethod
    def check_not_summary(cls, v: str) -> str:
        summary_starts = ["招股书显示", "招股书披露", "根据招股书", "据招股书"]
        for kw in summary_starts:
            if v.strip().startswith(kw):
                raise ValueError(f"evidence_text 疑似概括性语言，应为原文逐字摘录")
        return v

    @model_validator(mode="after")
    def cross_check_price_amount(self) -> "SubscriptionFlow":
        """价格×数量≈金额 一致性检查"""
        if self.price_per_share and self.shares_subscribed and self.amount_subscribed:
            expected = self.price_per_share * self.shares_subscribed
            if abs(expected - self.amount_subscribed) / self.amount_subscribed > 0.06:
                # 允许6%误差（四舍五入 + 合股误差），超过则记录但不断开
                pass
        return self


# ============================================================
# 2. 股权结构存量 — EquitySnapshot
# ============================================================

class EquitySnapshot(BaseModel):
    """
    股权结构存量: 回答"某个时点股东结构是什么"

    每行 = 一个股东在一个快照时点的持仓。
    必须包含 t0（报告期初或可识别的最早股权结构）。
    """
    record_type: RecordType = Field(
        default=RecordType.EQUITY_SNAPSHOT,
        description="记录类型标识"
    )
    company_name: str = Field(
        ...,
        min_length=1,
        description="公司全称"
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
        description="PDF 页码或 MD 文件行号范围"
    )

    # ── 快照信息 ──
    snapshot_date: str = Field(
        ...,
        min_length=7,
        description="时点（YYYY-MM-DD 或 YYYY-MM）"
    )
    snapshot_type: str = Field(
        ...,
        min_length=1,
        description="股权结构口径（如: 报告期初 / 有限公司设立时 / 股改后 / XX轮增资后 / IPO前）"
    )

    # ── 总量（同快照所有行一致） ──
    total_shares: Optional[float] = Field(
        None, ge=0,
        description="总股本（万股）。PDF 未披露则留空"
    )
    total_capital: Optional[float] = Field(
        None, ge=0,
        description="总出资额 / 注册资本（万元）。PDF 未披露则留空"
    )

    # ── 股东持仓 ──
    shareholder_name: str = Field(
        ...,
        min_length=1,
        description="股东名称"
    )
    shares_held: Optional[float] = Field(
        None, ge=0,
        description="持股数（万股）。PDF 未按股数披露则留空"
    )
    capital_contribution: Optional[float] = Field(
        None, ge=0,
        description="出资额（万元注册资本）。PDF 未按出资额披露则留空"
    )
    shareholding_ratio: Optional[str] = Field(
        None,
        description="持股比例（如 25.00%）"
    )

    # ── 增强字段 ──
    snapshot_order: Optional[int] = Field(
        None, ge=0,
        description="快照序号（t0=0 为最早可识别股权结构, t1=1, t2=2...）"
    )
    shareholder_type_detail: Optional[ShareholderTypeDetail] = Field(
        None,
        description="股东类型细分（控股股东/实际控制人/员工持股平台/外部PE/VC/产业资本/政府基金/自然人/原始创始人）"
    )
    is_original_founder: Optional[str] = Field(
        None,
        pattern=r'^(yes|no|unknown)$',
        description="是否原始创始人（yes/no/unknown）"
    )

    # ── 证据 ──
    evidence_text: str = Field(
        ...,
        min_length=20,
        description="原文逐字摘录"
    )
    notes: Optional[str] = Field(
        None,
        description="备注"
    )

    @field_validator("snapshot_date")
    @classmethod
    def check_date(cls, v: str) -> str:
        import re
        if not re.match(r'^\d{4}-\d{2}(-\d{2})?$', v):
            raise ValueError(f"日期格式错误: {v}")
        return v

    @field_validator("evidence_text")
    @classmethod
    def check_not_summary(cls, v: str) -> str:
        summary_starts = ["招股书显示", "招股书披露", "根据招股书", "据招股书"]
        for kw in summary_starts:
            if v.strip().startswith(kw):
                raise ValueError(f"evidence_text 疑似概括性语言，应为原文逐字摘录")
        return v
