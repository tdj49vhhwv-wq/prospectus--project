#!/usr/bin/env python3
"""Stage 5B.4 transport + document identity validator.

Consumes a resolver-produced manifest whose source_url values have already
passed official-host/title metadata checks. Downloads into raw_pdf, verifies
HTTP/PDF/size, extracts first pages, validates prospectus + issuer + stock code,
computes SHA256, and writes a new manifest. Any failure remains fail-closed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import re
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_IN = ROOT / "week10/acquisition/resolver_v1/acquisition_manifest_resolved_v1.csv"
DEFAULT_OUT = ROOT / "week10/acquisition/manifests/acquisition_manifest_validated_v1.csv"
RAW = ROOT / "week10/acquisition/raw_pdf"
LOG = ROOT / "week10/acquisition/logs/download_validation_v1.csv"

OFFICIAL_HOSTS = {
    "SSE": ("sse.com.cn",), "SZSE": ("szse.cn",), "BSE": ("bse.cn",),
}
MIN_BYTES = 200_000
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126 Safari/537.36"
NEGATIVE_DOCS = ("上市公告书", "招股说明书摘要", "招股意向书", "发行结果公告", "询价公告", "路演公告")


def official(exchange: str, url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in OFFICIAL_HOSTS.get(exchange, ()))


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "").lower()


def download(url: str) -> tuple[int, str, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/pdf,*/*"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read()


def text_first_pages(data: bytes, max_pages: int = 12) -> tuple[int, str]:
    reader = PdfReader(io.BytesIO(data), strict=False)
    parts = []
    for page in reader.pages[:max_pages]:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            parts.append("")
    return len(reader.pages), "\n".join(parts)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def identity(row: dict, text: str) -> tuple[bool, dict]:
    n = norm(text)
    code = norm(row["stock_code"])
    company = norm(row["company_name"])
    prospectus = "招股说明书" in n
    company_ok = company in n
    code_ok = code in n
    negative = next((x for x in NEGATIVE_DOCS if norm(x) in n[:12000]), "")
    # '招股意向书' can be quoted inside a valid prospectus, so only reject when
    # the document's opening region itself lacks 招股说明书.
    negative_opening = bool(negative) and "招股说明书" not in n[:5000]
    ok = prospectus and company_ok and code_ok and not negative_opening
    return ok, {
        "prospectus_match": prospectus, "issuer_match": company_ok,
        "stock_code_match": code_ok, "negative_opening": negative if negative_opening else "",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=DEFAULT_IN)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True); LOG.parent.mkdir(parents=True, exist_ok=True); args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.manifest.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    logs = []; output = []
    for row in rows:
        out = dict(row)
        url = (row.get("source_url") or "").strip()
        rec = {"sample_id": row.get("sample_id", ""), "stock_code": row["stock_code"], "company_name": row["company_name"],
               "exchange": row["exchange"], "source_url": url, "http_status": "", "content_type": "", "bytes": "", "pdf_magic": False,
               "page_count": "", "prospectus_match": False, "issuer_match": False, "stock_code_match": False,
               "sha256": "", "status": "", "error": ""}
        if row.get("download_status") != "resolved" or not url:
            rec["status"] = "SKIPPED_UNRESOLVED"; output.append(out); logs.append(rec); continue
        if not official(row["exchange"], url):
            rec["status"] = "REJECTED_NON_OFFICIAL"; rec["error"] = "unexpected host"; out["download_status"] = "validation_failed"; output.append(out); logs.append(rec); continue
        try:
            status, ctype, data = download(url)
            rec["http_status"] = status; rec["content_type"] = ctype; rec["bytes"] = len(data)
            rec["pdf_magic"] = data.startswith(b"%PDF-")
            if status != 200: raise RuntimeError(f"HTTP {status}")
            if not rec["pdf_magic"]: raise RuntimeError("missing %PDF magic")
            if len(data) < MIN_BYTES: raise RuntimeError(f"file too small: {len(data)}")
            pages, text = text_first_pages(data)
            rec["page_count"] = pages
            ok, checks = identity(row, text)
            rec.update(checks)
            if not ok:
                raise RuntimeError("document identity validation failed")
            digest = sha256_bytes(data); rec["sha256"] = digest
            safe_company = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "_", row["company_name"])
            dest = RAW / f'{row["stock_code"]}_{safe_company}_招股说明书.pdf'
            dest.write_bytes(data)
            out["pdf_path"] = str(dest.relative_to(ROOT)); out["sha256"] = digest; out["download_status"] = "downloaded_validated"
            out["notes"] = (out.get("notes", "") + f"; pages={pages}; bytes={len(data)}").strip("; ")
            rec["status"] = "DOWNLOADED_VALIDATED"
        except Exception as e:
            out["download_status"] = "validation_failed"; out["notes"] = (out.get("notes", "") + f"; validation_error={type(e).__name__}:{e}").strip("; ")
            rec["status"] = "FAILED"; rec["error"] = f"{type(e).__name__}:{e}"
        output.append(out); logs.append(rec)

    fields = list(rows[0].keys()) if rows else []
    with args.out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(output)
    lfields = list(logs[0].keys()) if logs else []
    with LOG.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=lfields); w.writeheader(); w.writerows(logs)
    print("===== DOWNLOAD + VALIDATION =====")
    for r in logs: print(r["stock_code"], r["status"], r["bytes"] or "-", r["sha256"][:12] if r["sha256"] else "-")
    print("Validated:", sum(r["status"] == "DOWNLOADED_VALIDATED" for r in logs), "/", len(logs))
    print("Manifest:", args.out.relative_to(ROOT)); print("Log:", LOG.relative_to(ROOT))

if __name__ == "__main__":
    main()
