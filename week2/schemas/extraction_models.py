"""
Pydantic 抽取模型 — Week 2 交付

两类基础事实记录:
  1. SubscriptionFlow  — 认缴流量: 谁在什么时候认购了多少、多少钱、什么价格
     - 字段: source_page, subscription_date, subscriber_name,
             shares_subscribed, amount_subscribed, price_per_share, evidence_text
  2. EquitySnapshot   — 股权结构存量: 某个时点的股东结构
     - 字段: source_page, snapshot_date, snapshot_type,
             total_shares, total_capital, shareholder_name,
             shares_held, capital_contribution, shareholding_ratio, evidence_text

规则: PDF只披露出资额→只填出资额; PDF只披露持股数→只填持股数; 不要倒推。
"""
from .models import (
    SubscriptionFlow,
    EquitySnapshot,
    RecordType,
    Currency,
)

__all__ = [
    "SubscriptionFlow",
    "EquitySnapshot",
    "RecordType",
    "Currency",
]
