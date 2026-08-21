#!/usr/bin/env python3
"""Shared helpers for the SSE/SZSE/BSE discovery adapters.

Every adapter returns a list of :class:`Candidate` dataclasses.  A candidate
is only a *URL + metadata* — it is NOT yet trusted.  Downstream acquisition
(stage acquire.py) re-validates transport + document identity before a PDF
enters the canonical registry, so discovery here is allowed to be permissive
about the URL itself and strict about which title qualifies as a final
prospectus.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

import requests

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# A final issuance prospectus carries one of these terms.
PROSPECTUS_TERMS = ("招股说明书", "招股书")

# Any of these terms in the title means it is NOT the final prospectus
# (draft, summary, notice, letter, etc.).  Fail-closed: exclude on sight.
NEGATIVE_TERMS = (
    "提示性公告",
    "摘要",
    "上市公告书",
    "发行结果",
    "询价",
    "路演",
    "意向书",
    "上会稿",
    "注册稿",
    "申报稿",
    "核查意见",
    "法律意见",
    "发行公告",
    "发行安排",
    "附录",
)


@dataclass
class Candidate:
    stock_code: str
    company_name: str
    exchange: str
    url: str
    title: str = ""
    source: str = ""
    document_date: str = ""
    matched_code: str = ""
    matched_name: str = ""


def normalize(s: str) -> str:
    """Strip all whitespace so PDF-extracted CJK text matches cleanly."""
    return re.sub(r"\s+", "", s or "")


def strip_em(s: str) -> str:
    return (s or "").replace("<em>", "").replace("</em>", "").strip()


def is_final_prospectus(title: str) -> bool:
    t = normalize(strip_em(title))
    has_prospectus = any(normalize(p) in t for p in PROSPECTUS_TERMS)
    has_negative = any(normalize(n) in t for n in NEGATIVE_TERMS)
    return has_prospectus and not has_negative


def date_window(disclosure_date: str, days: int = 75) -> str:
    """Return a cninfo `seDate` range string around a disclosure date."""
    d = datetime.strptime(disclosure_date, "%Y-%m-%d")
    start = (d - timedelta(days=days)).strftime("%Y-%m-%d")
    end = (d + timedelta(days=days)).strftime("%Y-%m-%d")
    return f"{start}~{end}"


def epoch_ms_to_date(ms) -> str:
    """cninfo announcementTime (epoch ms) -> Beijing 'YYYY-MM-DD'."""
    try:
        dt = datetime.utcfromtimestamp(int(ms) / 1000) + timedelta(hours=8)
        return dt.strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return ""


def http_get(url, params=None, referer="", timeout=30):
    headers = {"User-Agent": USER_AGENT}
    if referer:
        headers["Referer"] = referer
    return requests.get(url, params=params, headers=headers, timeout=timeout)


def http_post(url, data=None, referer="", timeout=30):
    headers = {"User-Agent": USER_AGENT}
    if referer:
        headers["Referer"] = referer
    return requests.post(url, data=data, headers=headers, timeout=timeout)
