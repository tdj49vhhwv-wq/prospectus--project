#!/usr/bin/env python3
"""Stage 5C — conversion quality check for DEV 12 canonical Markdown.

After MinerU conversion, verify each canonical `.md` is a structurally sane
prospectus before running the Structure Profiler v2. Reports, per issuer:

  - character_count, line_count, heading_count, html_table_count,
    date_expression_count, page_marker_count
  - flag: too_short (< 100k chars), few_headings (< 80), few_tables (< 30),
    no_dates (< 100)

This is a conversion-sanity gate, NOT part of the routing signals.
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CANONICAL_DIR = ROOT / "week10/canonical"
MANIFEST = ROOT / "week10/acquisition/manifests/acquisition_manifest_v1.csv"
OUT = ROOT / "week10/canonical/quality_check_v1.csv"


def date_count(text: str) -> int:
    patterns = [
        r"(?:19|20)\d{2}\s*年\s*\d{1,2}\s*月(?:\s*\d{1,2}\s*日)?",
        r"(?:19|20)\d{2}[-/.]\d{1,2}(?:[-/.]\d{1,2})?",
    ]
    return sum(len(re.findall(p, text)) for p in patterns)


def main() -> None:
    with MANIFEST.open(newline="", encoding="utf-8") as fh:
        rows = [dict(r) for r in csv.DictReader(fh)]
    dev = [
        {k.lstrip("﻿"): v for k, v in r.items()}
        for r in rows if r.get("role") == "DEV"
    ]

    results = []
    print(f"{'code':>8} {'board':<8} {'chars':>8} {'lines':>7} "
          f"{'head':>5} {'tables':>6} {'dates':>6} {'pages':>6}  flags")
    for r in sorted(dev, key=lambda x: x["stock_code"]):
        code = r["stock_code"]
        stem = Path(r["pdf_path"]).stem
        md = CANONICAL_DIR / f"{stem}.md"
        if not md.exists():
            print(f"{code:>8} {r['board']:<8} MISSING canonical md")
            results.append({
                "stock_code": code, "board": r["board"],
                "company_name": r["company_name"], "status": "missing",
            })
            continue

        text = md.read_text(encoding="utf-8")
        lines = text.splitlines()
        headings = len([
            l for l in lines if re.match(r"^\s{0,3}#{1,6}\s+\S", l)
        ])
        tables = len(re.findall(r"<table\b", text, re.I))
        dates = date_count(text)
        pages = len(re.findall(r"##\s*第\s*\d+\s*页", text))

        flags = []
        if len(text) < 100_000:
            flags.append("too_short")
        if headings < 80:
            flags.append("few_headings")
        if tables < 30:
            flags.append("few_tables")
        if dates < 100:
            flags.append("no_dates")

        print(f"{code:>8} {r['board']:<8} {len(text):>8} {len(lines):>7} "
              f"{headings:>5} {tables:>6} {dates:>6} {pages:>6}  "
              f"{','.join(flags) if flags else 'OK'}")

        results.append({
            "stock_code": code, "board": r["board"],
            "company_name": r["company_name"], "status": "ok",
            "character_count": len(text), "line_count": len(lines),
            "heading_count": headings, "html_table_count": tables,
            "date_expression_count": dates, "page_marker_count": pages,
            "flags": ",".join(flags),
        })

    with OUT.open("w", newline="", encoding="utf-8-sig") as fh:
        fields = list(results[0].keys())
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(results)

    n_bad = sum(1 for x in results if x.get("flags") or x.get("status") != "ok")
    print(f"\n{len(results)} DEV docs checked, {n_bad} flagged")
    print("Output:", OUT.relative_to(ROOT))


if __name__ == "__main__":
    sys.exit(main())
