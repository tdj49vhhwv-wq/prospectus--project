#!/usr/bin/env python3
"""Generate ``acquisition_manifest_v1.csv`` from the frozen stage-5 sample.

Maps each of the 24 independent-sample issuers (S501-S524) to its exchange
route (SSE / SZSE / BSE) and seeds the manifest columns the acquisition
pipeline fills in.  The three smoke-test issuers keep their known disclosure
dates; the rest start empty and are resolved by the discovery adapters.
"""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SAMPLING = ROOT / "week10/universe/stage5_sampling_manifest_v1.csv"
OUT = ROOT / "week10/acquisition/manifests/acquisition_manifest_v1.csv"

# The three smoke-test issuers already validated end-to-end.
KNOWN_DISCLOSURE_DATE = {
    "603312": "2024-01-08",  # 西典新能 (SSE Main)
    "301536": "2024-03-22",  # 星宸科技 (SZSE ChiNext)
    "920002": "2024-05-17",  # 万达轴承 (BSE)
}

FIELDS = [
    "sample_id", "role", "board", "year", "stock_code", "company_name",
    "exchange", "disclosure_date", "source_url", "source_type",
    "download_status", "pdf_path", "pdf_bytes", "sha256", "notes",
]


def exchange_for(code: str) -> str:
    if code.startswith("920"):
        return "BSE"
    if code.startswith("60"):
        return "SSE"
    return "SZSE"  # 000/001/002/003 main board + 300/301 ChiNext


def main() -> None:
    with SAMPLING.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    out_rows = []
    for r in rows:
        code = r["stock_code"].strip()
        out_rows.append({
            "sample_id": r["sample_id"],
            "role": r["role"],
            "board": r["board"],
            "year": r["year"],
            "stock_code": code,
            "company_name": r["company_name"],
            "exchange": exchange_for(code),
            "disclosure_date": KNOWN_DISCLOSURE_DATE.get(code, ""),
            "source_url": "",
            "source_type": "",
            "download_status": "pending",
            "pdf_path": "",
            "pdf_bytes": "",
            "sha256": "",
            "notes": "",
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(out_rows)

    print(f"Wrote {len(out_rows)} rows -> {OUT.relative_to(ROOT)}")
    for r in out_rows:
        print(f"  {r['sample_id']} {r['stock_code']} {r['company_name']} "
              f"{r['exchange']} date={r['disclosure_date'] or '(resolve)'}")


if __name__ == "__main__":
    main()
