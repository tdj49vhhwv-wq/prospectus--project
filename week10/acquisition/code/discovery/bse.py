#!/usr/bin/env python3
"""BSE (Beijing) discovery adapter.

BSE issuers are not covered by cninfo, so this adapter queries the BSE-native
disclosure API directly.  ``zoneInfoResult.do`` with ``disclosureTypes[]=9533``
(招股说明书) and a keyword filter returns JSONP whose ``listInfo.content``
carries ``destFilePath`` (relative PDF path) and ``publishDate``.
"""
from __future__ import annotations

import re

from .base import Candidate, http_get, is_final_prospectus, strip_em

BSE_QUERY = "https://www.bse.cn/disclosureInfoController/zoneInfoResult.do"
BSE_REFERER = "https://www.bse.cn/"
BSE_BASE = "https://www.bse.cn"


def _strip_jsonp(text: str) -> str:
    m = re.search(r"\[.*\]", text, re.S)
    return m.group(0) if m else ""


def discover(stock_code, company_name, date_range):
    params = {
        "keyword": "招股说明书",
        "companyCd": stock_code,
        "disclosureTypes[]": "9533",  # 9533 = 招股说明书; required or BSE returns 请求参数异常
        "page": "0",
        "needFields[]": [
            "companyCd",
            "companyName",
            "disclosureTitle",
            "destFilePath",
            "publishDate",
            "fileExt",
        ],
        "sortfield": "xxssdq",
        "sorttype": "asc",
    }
    resp = http_get(BSE_QUERY, params=params, referer=BSE_REFERER, timeout=30)
    resp.raise_for_status()

    import json

    payload = json.loads(_strip_jsonp(resp.text))
    if not payload or "listInfo" not in payload[0]:
        return []
    content = payload[0]["listInfo"]["content"] or []

    out = []
    for item in content:
        title = strip_em(item.get("disclosureTitle", ""))
        # Keep only titles that are the final prospectus; skip notices/letters.
        if not is_final_prospectus(title):
            continue
        dest = (item.get("destFilePath") or "").strip()
        if not dest:
            continue
        out.append(
            Candidate(
                stock_code=stock_code,
                company_name=company_name,
                exchange="BSE",
                url=BSE_BASE + dest,
                title=title,
                source="bse_official",
                document_date=item.get("publishDate", ""),
                matched_code=(item.get("companyCd") or "").strip(),
                matched_name=(item.get("companyName") or "").strip(),
            )
        )
    return out
