"""
Pydantic Schema 定义 — Week 2 融资历史抽取

两类基础事实记录：
  1. SubscriptionFlow  — 认缴流量: 谁在什么时候认购了多少、多少钱、什么价格
  2. EquitySnapshot   — 股权结构存量: 某个时点的股东结构
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
