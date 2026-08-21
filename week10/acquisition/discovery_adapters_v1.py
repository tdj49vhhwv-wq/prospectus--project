#!/usr/bin/env python3
"""Stage 5B.4 exchange-specific discovery adapters.

Design goals:
- SSE/SZSE/BSE are separate adapters.
- Discovery emits candidates only; it never marks a document canonical.
- Third-party search results may be ingested only as hints. Canonical acceptance
  remains restricted to the expected official exchange host.
- Fail closed on network/API changes.

This module intentionally centralizes exchange behavior so the downloader and
validator stay exchange-agnostic.
"""
from __future__ import annotations

import csv
import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "week10/acquisition/manifests/acquisition_manifest_v1.csv"
DEFAULT_OUT = ROOT / "week10/acquisition/resolver_v1/discovered_candidates_v1.csv"

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126 Safari/537.36"

@dataclass
class DiscoveryCandidate:
    stock_code: str
    company_name: str
    exchange: str
    url: str
    title: str
    source: str
    discovery_status: str = "candidate"
    discovery_notes: str = ""


def get(url: str, headers: dict | None = None, timeout: int = 25) -> tuple[int, str, bytes]:
    h = {"User-Agent": UA, "Accept": "application/json,text/html,application/pdf,*/*"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.headers.get("Content-Type", ""), resp.read()


def extract_pdf_links(blob: str, base: str) -> list[tuple[str, str]]:
    """Best-effort HTML/JSON link extractor; validation happens downstream."""
    out: list[tuple[str, str]] = []
    # href/src JSON values and escaped paths
    patterns = [
        r'(?P<url>https?://[^"\'<>\\ ]+?\.pdf(?:\?[^"\'<>\\ ]*)?)',
        r'(?P<url>/[^"\'<> ]+?\.pdf(?:\?[^"\'<> ]*)?)',
        r'(?P<url>[^"\']+?\.PDF(?:\?[^"\']*)?)',
    ]
    for pat in patterns:
        for m in re.finditer(pat, blob, flags=re.I):
            raw = m.group("url").replace("\\/", "/")
            url = urllib.parse.urljoin(base, raw)
            # nearby text is useful as a title hint
            s = max(0, m.start() - 180); e = min(len(blob), m.end() + 180)
            nearby = re.sub(r"<[^>]+>", " ", blob[s:e])
            nearby = re.sub(r"\s+", " ", nearby).strip()
            out.append((url, nearby))
    # stable dedupe
    seen = set(); dedup = []
    for x in out:
        if x[0] not in seen:
            seen.add(x[0]); dedup.append(x)
    return dedup


class BaseAdapter:
    exchange = ""
    def discover(self, row: dict) -> list[DiscoveryCandidate]:
        raise NotImplementedError

    def wrap(self, row: dict, url: str, title: str, source: str, notes: str = "") -> DiscoveryCandidate:
        return DiscoveryCandidate(row["stock_code"], row["company_name"], self.exchange,
                                  url, title, source, "candidate", notes)


class SSEAdapter(BaseAdapter):
    exchange = "SSE"
    def discover(self, row: dict) -> list[DiscoveryCandidate]:
        code = row["stock_code"]
        # Listed-company disclosure endpoint. For IPO-stage docs it may return no
        # result, but it is a stable official first hop and useful for final prospectus.
        params = {
            "isPagination": "true", "productId": code,
            "securityType": "0101,120100,020100,020200,120200",
            "reportType": "ALL", "beginDate": f'{row["year"]}-01-01',
            "endDate": f'{row["year"]}-12-31', "pageHelp.pageSize": "100",
            "pageHelp.pageNo": "1", "pageHelp.beginPage": "1", "pageHelp.endPage": "5",
        }
        url = "https://query.sse.com.cn/security/stock/queryCompanyBulletin.do?" + urllib.parse.urlencode(params)
        try:
            _, _, data = get(url, {"Referer": "https://www.sse.com.cn/"})
            text = data.decode("utf-8", "ignore")
            items = []
            for pdf, nearby in extract_pdf_links(text, "https://www.sse.com.cn/"):
                if "招股" in nearby or "prospectus" in nearby.lower():
                    items.append(self.wrap(row, pdf, nearby, "sse_queryCompanyBulletin"))
            return items
        except Exception as e:
            return [self.wrap(row, "", "", "sse_queryCompanyBulletin", f"adapter_error:{type(e).__name__}:{e}")]


class SZSEAdapter(BaseAdapter):
    exchange = "SZSE"
    def discover(self, row: dict) -> list[DiscoveryCandidate]:
        # SZSE announcement page is JS-backed. Query the official page with issuer
        # parameters and parse any embedded/static PDF links. This adapter is kept
        # separate because SZSE changes JSON endpoints more frequently than SSE.
        code = row["stock_code"]
        pages = [
            f"https://www.szse.cn/disclosure/listed/bulletinDetail/index.html?{urllib.parse.urlencode({'code': code})}",
            f"https://www.szse.cn/disclosure/listed/notice/index.html?{urllib.parse.urlencode({'stock': code})}",
        ]
        found: list[DiscoveryCandidate] = []
        errors = []
        for page in pages:
            try:
                _, _, data = get(page, {"Referer": "https://www.szse.cn/"})
                text = data.decode("utf-8", "ignore")
                for pdf, nearby in extract_pdf_links(text, "https://www.szse.cn/"):
                    if "招股" in nearby or "prospectus" in nearby.lower():
                        found.append(self.wrap(row, pdf, nearby, "szse_official_page"))
            except Exception as e:
                errors.append(f"{type(e).__name__}:{e}")
        if not found and errors:
            found.append(self.wrap(row, "", "", "szse_official_page", "adapter_error:" + "|".join(errors)))
        return found


class BSEAdapter(BaseAdapter):
    exchange = "BSE"
    def discover(self, row: dict) -> list[DiscoveryCandidate]:
        code = row["stock_code"]
        # BSE listing disclosure page provides the canonical official host. The
        # dynamic backend is intentionally not guessed here; candidate extraction
        # falls back to links exposed by official pages and later can be extended
        # without touching validator/downloader semantics.
        pages = [
            f"https://www.bse.cn/disclosure/announcement.html?{urllib.parse.urlencode({'stockCode': code})}",
            "https://www.bse.cn/disclosure/announcement.html",
        ]
        found: list[DiscoveryCandidate] = []
        errors = []
        for page in pages:
            try:
                _, _, data = get(page, {"Referer": "https://www.bse.cn/"})
                text = data.decode("utf-8", "ignore")
                for pdf, nearby in extract_pdf_links(text, "https://www.bse.cn/"):
                    if (code in nearby or row["company_name"] in nearby) and "招股" in nearby:
                        found.append(self.wrap(row, pdf, nearby, "bse_official_page"))
            except Exception as e:
                errors.append(f"{type(e).__name__}:{e}")
        if not found and errors:
            found.append(self.wrap(row, "", "", "bse_official_page", "adapter_error:" + "|".join(errors)))
        return found


ADAPTERS = {"SSE": SSEAdapter(), "SZSE": SZSEAdapter(), "BSE": BSEAdapter()}


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    with args.manifest.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    all_candidates: list[DiscoveryCandidate] = []
    for row in rows:
        adapter = ADAPTERS.get(row["exchange"])
        if not adapter:
            all_candidates.append(DiscoveryCandidate(row["stock_code"], row["company_name"], row["exchange"], "", "", "none", "unsupported_exchange", ""))
            continue
        cs = adapter.discover(row)
        if not cs:
            all_candidates.append(DiscoveryCandidate(row["stock_code"], row["company_name"], row["exchange"], "", "", adapter.__class__.__name__, "no_candidate", "official discovery returned no prospectus candidate"))
        else:
            all_candidates.extend(cs)
        time.sleep(0.2)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fields = list(DiscoveryCandidate.__dataclass_fields__)
    with args.out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(asdict(x) for x in all_candidates)
    print("===== EXCHANGE DISCOVERY =====")
    print("Rows:", len(rows))
    print("Candidates/log rows:", len(all_candidates))
    for x in all_candidates:
        print(x.exchange, x.stock_code, x.discovery_status, x.url or "-")
    print("Output:", args.out.relative_to(ROOT))

if __name__ == "__main__":
    main()
