#!/usr/bin/env python3
"""SZSE (Shenzhen) discovery adapter.

Same rationale as :mod:`discovery.sse`: the SZSE-native disclosure search
(szse.cn ``ShowReport``) is not reliably queryable, while cninfo — the
CSRC-designated official disclosure platform — hosts the identical official
PDF for SZSE-listed issuers.  Discover via cninfo ``column=szse``.
"""
from __future__ import annotations

from .base import Candidate, epoch_ms_to_date, http_post, is_final_prospectus, strip_em

CNINFO_QUERY = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_REFERER = "http://www.cninfo.com.cn/new/disclosure/"
PDF_BASE = "http://static.cninfo.com.cn/"


def discover(stock_code, company_name, date_range):
    params = {
        "pageNum": "1",
        "pageSize": "30",
        "column": "szse",
        "tabName": "fulltext",
        "plate": "",
        "stock": "",
        "searchkey": f"{stock_code} 招股说明书",
        "secid": "",
        "category": "",
        "trade": "",
        "seDate": date_range,
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }
    resp = http_post(CNINFO_QUERY, data=params, referer=CNINFO_REFERER, timeout=30)
    resp.raise_for_status()
    announcements = resp.json().get("announcements") or []

    out = []
    for a in announcements:
        title = strip_em(a.get("announcementTitle", ""))
        if not is_final_prospectus(title):
            continue
        adjunct = (a.get("adjunctUrl") or "").strip()
        if not adjunct:
            continue
        out.append(
            Candidate(
                stock_code=stock_code,
                company_name=company_name,
                exchange="SZSE",
                url=PDF_BASE + adjunct,
                title=title,
                source="cninfo_official",
                document_date=epoch_ms_to_date(a.get("announcementTime")),
                matched_code=(a.get("secCode") or "").strip(),
            )
        )
    return out
