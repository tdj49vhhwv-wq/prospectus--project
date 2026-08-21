#!/usr/bin/env python3

import csv
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

MANIFEST = (
    ROOT
    / "week10/acquisition/manifests/"
      "resolved_sources_v1.csv"
)

OUT = (
    ROOT
    / "week10/acquisition/logs/"
      "resolver_candidate_validation_v1.csv"
)


def fetch_head(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent":
                "Mozilla/5.0 prospectus-research/1.0",
            "Accept":
                "application/pdf,text/html,*/*",
        },
    )

    with urllib.request.urlopen(
        req,
        timeout=30
    ) as resp:

        content_type = (
            resp.headers.get("Content-Type", "")
        )

        data = resp.read(300000)

    return content_type, data


def validate_pdf_bytes(
    data,
    stock_code,
    company_name,
):
    """
    Lightweight transport validation only.

    Content-level title validation happens after PDF text
    extraction in Stage 5B.4.
    """

    reasons = []

    pdf_ok = data.startswith(b"%PDF-")

    if not pdf_ok:
        reasons.append("not_pdf")

    if len(data) < 100000:
        reasons.append("small_response")

    return pdf_ok, reasons


with MANIFEST.open(
    encoding="utf-8-sig"
) as f:
    rows = list(csv.DictReader(f))


print()
print("===== RESOLVER CANDIDATE VALIDATION =====")

results = []

for r in rows:

    url = r["source_url"].strip()

    out = {
        "sample_id": r["sample_id"],
        "stock_code": r["stock_code"],
        "company_name": r["company_name"],
        "exchange": r["exchange"],
        "source_url": url,
        "transport_status": "",
        "content_type": "",
        "notes": "",
    }

    print()
    print(
        r["stock_code"],
        r["company_name"],
        r["exchange"],
    )

    if not url:

        out["transport_status"] = "UNRESOLVED"
        out["notes"] = "source_url empty"

        print("  source_url: EMPTY")
        print("  status    : UNRESOLVED")

        results.append(out)
        continue

    try:

        content_type, data = fetch_head(url)

        ok, reasons = validate_pdf_bytes(
            data,
            r["stock_code"],
            r["company_name"],
        )

        out["content_type"] = content_type

        if ok:
            out["transport_status"] = "PDF_REACHABLE"
            print("  status    : PDF_REACHABLE")
        else:
            out["transport_status"] = "INVALID"
            out["notes"] = ";".join(reasons)
            print("  status    : INVALID")
            print("  reasons   :", reasons)

        print("  type      :", content_type)

    except Exception as e:

        out["transport_status"] = "FAILED"
        out["notes"] = repr(e)

        print("  status    : FAILED")
        print("  error     :", repr(e))

    results.append(out)


with OUT.open(
    "w",
    newline="",
    encoding="utf-8-sig",
) as f:

    fields = list(results[0].keys())

    w = csv.DictWriter(
        f,
        fieldnames=fields
    )

    w.writeheader()
    w.writerows(results)


print()
print("Output:")
print(" ", OUT.relative_to(ROOT))
