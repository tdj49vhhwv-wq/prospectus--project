#!/usr/bin/env python3

import csv
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[3]

P = (
    ROOT
    / "week10/acquisition/manifests/resolved_sources_v1.csv"
)

with P.open(
    encoding="utf-8-sig"
) as f:
    rows = list(csv.DictReader(f))


print("===== RESOLVER STATUS =====")

for r in rows:

    print(
        r["stock_code"],
        r["company_name"],
        r["exchange"],
        r["document_date"],
        r["resolution_status"],
        r["source_domain"] or "-",
    )


print()
print(
    "Status:",
    dict(
        Counter(
            r["resolution_status"]
            for r in rows
        )
    )
)

print()
print(
    "Resolved URLs:",
    sum(
        bool(r["source_url"].strip())
        for r in rows
    ),
    "/",
    len(rows)
)
