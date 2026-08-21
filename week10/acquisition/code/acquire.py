#!/usr/bin/env python3
"""Week 10 Stage 5B — end-to-end prospectus acquisition pipeline.

Gate chain, fail-closed (any failure stops the row; no silent replacement):

    discovery (official URL)
    -> HTTP 200
    -> %PDF magic bytes
    -> minimum file size
    -> prospectus title        (身份校验)
    -> issuer identity         (身份校验)
    -> stock code              (身份校验)
    -> SHA256
    -> manifest status = downloaded_validated

The input manifest is ``manifests/acquisition_manifest_v1.csv``; it is updated
in place with source_url / download_status / pdf_path / sha256 after the run.
"""
from __future__ import annotations

import csv
import hashlib
import time
from pathlib import Path

import fitz  # PyMuPDF
import requests

from discovery import discover
from discovery.base import date_window, normalize

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "week10/acquisition/manifests/acquisition_manifest_v1.csv"
RAW_PDF_DIR = ROOT / "week10/acquisition/raw_pdf"
LOG = ROOT / "week10/acquisition/logs/acquire_results_v1.csv"

MIN_PDF_BYTES = 500_000          # full prospectuses are MB-scale; reject tiny/HTML
MAX_IDENTITY_PAGES = 20          # cover + notices + TOC carry title/issuer/code

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}
REFERER = {
    "cninfo_official": "http://www.cninfo.com.cn/",
    "bse_official": "https://www.bse.cn/",
}

# Manifest columns that acquire.py updates.
UPDATABLE = [
    "disclosure_date", "source_url", "source_type", "download_status",
    "pdf_path", "pdf_bytes", "sha256", "notes",
]


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download(url: str, source: str) -> bytes:
    req_headers = dict(UA)
    req_headers["Referer"] = REFERER.get(source, "")
    resp = requests.get(url, headers=req_headers, timeout=90)
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}")
    return resp.content


def extract_identity_text(data: bytes) -> str:
    doc = fitz.open(stream=data, filetype="pdf")
    pages = min(doc.page_count, MAX_IDENTITY_PAGES)
    text = "".join(doc[i].get_text() for i in range(pages))
    doc.close()
    return text


def validate_identity(data: bytes, company_name: str, stock_code: str):
    """Content identity: title + issuer must be present in extracted text.

    Returns ``(ok, reasons, code_in_text)``.  The stock code is *not* a hard
    content gate here because SSE/SZSE covers often render it as a graphic the
    text layer omits; the code is instead verified against official discovery
    metadata (cninfo ``secCode`` / bse.cn ``companyCd``) in :func:`run`.
    """
    text = normalize(extract_identity_text(data))
    reasons = []

    if "招股说明书" not in text:
        reasons.append("no_prospectus_title")
    if normalize(company_name) not in text:
        reasons.append("issuer_mismatch")
    code_in_text = stock_code in text

    return (not reasons), reasons, code_in_text


def run():
    RAW_PDF_DIR.mkdir(parents=True, exist_ok=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)

    with MANIFEST.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    results = []
    for row in rows:
        code = row["stock_code"].strip()
        company = row["company_name"].strip()
        exchange = row["exchange"].strip().upper()
        ddate = row["disclosure_date"].strip()
        year = row["year"].strip()

        rec = {k: row.get(k, "") for k in UPDATABLE}

        # Idempotency: skip rows already validated with a verified on-disk PDF.
        if (
            row.get("download_status") == "downloaded_validated"
            and row.get("sha256")
            and row.get("pdf_path")
        ):
            p = ROOT / row["pdf_path"]
            if p.exists() and sha256_of(p.read_bytes()) == row["sha256"]:
                results.append({"row": row, "rec": rec, "err": ""})
                print(f"\n===== {code} {company} ({exchange}) =====")
                print("  skip   : already downloaded_validated")
                continue

        date_range = (
            date_window(ddate, 75)
            if ddate
            else f"{int(year) - 1}-01-01~{year}-12-31"
        )

        rec["download_status"] = "pending"
        rec["notes"] = ""

        err = ""
        print(f"\n===== {code} {company} ({exchange}) =====")

        try:
            # 1. discovery (retry: cninfo intermittently returns an empty list)
            candidates = []
            for attempt in range(3):
                candidates = discover(exchange, code, company, date_range)
                if candidates:
                    break
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
            if not candidates:
                raise _Gate("discovery_failed", "no official prospectus candidate discovered")
            cand = candidates[0]
            rec["source_url"] = cand.url
            rec["source_type"] = cand.source
            rec["notes"] = cand.title
            if not ddate and cand.document_date:
                rec["disclosure_date"] = cand.document_date
            print(f"  resolved: {cand.title}")
            print(f"  url     : {cand.url}")

            # 2. download (HTTP 200)
            data = download(cand.url, cand.source)
            print(f"  bytes   : {len(data):,}")

            # 3. %PDF magic
            if not data.startswith(b"%PDF-"):
                raise _Gate("not_pdf", "bad magic bytes")

            # 4. minimum file size
            if len(data) < MIN_PDF_BYTES:
                raise _Gate("too_small", f"{len(data)} bytes < {MIN_PDF_BYTES}")

            # 5-6. identity (content): title + issuer
            ok, reasons, code_in_text = validate_identity(data, company, code)
            if not ok:
                raise _Gate("identity_failed", ";".join(reasons))

            # 7. stock code: verified against official discovery metadata,
            #    falling back to content text presence.  BSE disclosure records
            #    carry a pre-renumbering (新三板) ``companyCd``, so for BSE the
            #    issuer name from metadata is the authoritative identity signal.
            meta_name_ok = bool(
                cand.matched_name
                and normalize(cand.matched_name) == normalize(company)
            )
            if cand.matched_code and cand.matched_code == code:
                code_note = "code_in_text" if code_in_text else "code_via_metadata"
            elif meta_name_ok:
                code_note = "name_via_metadata"
                if cand.matched_code:
                    code_note += f"_legacy_{cand.matched_code}"
            elif code_in_text:
                code_note = "code_in_text"
            else:
                raise _Gate(
                    "code_mismatch",
                    "code absent from metadata and text",
                )
            print(f"  identity: title+issuer OK; code ({code_note})")

            # 8. sha256 + persist
            digest = sha256_of(data)
            fname = f"{code}_{company}_招股说明书.pdf"
            out = RAW_PDF_DIR / fname
            out.write_bytes(data)

            rec["download_status"] = "downloaded_validated"
            rec["pdf_path"] = str(out.relative_to(ROOT))
            rec["pdf_bytes"] = str(len(data))
            rec["sha256"] = digest
            rec["notes"] = f"{cand.title}; {code_note}"
            print(f"  sha256  : {digest}")
            print(f"  status  : downloaded_validated")

        except _Gate as g:
            rec["download_status"] = g.status
            rec["notes"] = g.reason
            err = g.reason
            print(f"  {g.status.upper()}: {g.reason}")
        except Exception as e:
            rec["download_status"] = "failed"
            rec["notes"] = str(e)
            err = str(e)
            print(f"  FAILED  : {e}")

        results.append({"row": row, "rec": rec, "err": err})

    # write back manifest
    out_fields = [
        "sample_id", "role", "board", "year", "stock_code", "company_name",
        "exchange", "disclosure_date", "source_url", "source_type",
        "download_status", "pdf_path", "pdf_bytes", "sha256", "notes",
    ]
    with MANIFEST.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
        w.writeheader()
        for item in results:
            merged = dict(item["row"])
            merged.update(item["rec"])
            w.writerow(merged)

    # write run log
    log_fields = ["sample_id", "stock_code", "company_name", "exchange",
                  "source_url", "source_type", "download_status",
                  "pdf_path", "pdf_bytes", "sha256", "error"]
    with LOG.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=log_fields, extrasaction="ignore")
        w.writeheader()
        for item in results:
            r = item["row"]
            rec = item["rec"]
            w.writerow({
                "sample_id": r["sample_id"],
                "stock_code": r["stock_code"],
                "company_name": r["company_name"],
                "exchange": r["exchange"],
                "source_url": rec.get("source_url", ""),
                "source_type": rec.get("source_type", ""),
                "download_status": rec.get("download_status", ""),
                "pdf_path": rec.get("pdf_path", ""),
                "pdf_bytes": rec.get("pdf_bytes", ""),
                "sha256": rec.get("sha256", ""),
                "error": item["err"],
            })

    print("\n===== SUMMARY =====")
    for item in results:
        r = item["row"]
        rec = item["rec"]
        print(f"  {r['stock_code']} {r['company_name']}: {rec['download_status']}")
    print(f"\nManifest: {MANIFEST.relative_to(ROOT)}")
    print(f"Log     : {LOG.relative_to(ROOT)}")


class _Gate(Exception):
    """Fail-closed gate signal with a named status and reason."""

    def __init__(self, status, reason):
        super().__init__(reason)
        self.status = status
        self.reason = reason


if __name__ == "__main__":
    run()
