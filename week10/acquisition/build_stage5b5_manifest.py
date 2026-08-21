#!/usr/bin/env python3
"""Build Stage 5B.5 batch acquisition manifest only after 3/3 smoke pass."""
from __future__ import annotations
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SMOKE = ROOT / "week10/acquisition/manifests/acquisition_manifest_validated_v1.csv"
FROZEN = ROOT / "week10/universe/stage5_sampling_manifest_v1.csv"
OUT = ROOT / "week10/acquisition/manifests/acquisition_manifest_24_v1.csv"


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def exchange_for(row):
    board=row["board"]
    code=row["stock_code"]
    if board == "BSE": return "BSE"
    if board == "ChiNext": return "SZSE"
    # Main contains both SSE 60xxxx and SZSE 00/001xxx
    return "SSE" if code.startswith("6") else "SZSE"


def main():
    if not SMOKE.exists():
        raise SystemExit("BLOCKED: smoke validated manifest missing; Stage 5B.5 may not start")
    smoke=read(SMOKE)
    ok=[r for r in smoke if r.get("download_status") == "downloaded_validated"]
    exchanges={r["exchange"] for r in ok}
    if len(ok) != 3 or exchanges != {"SSE","SZSE","BSE"}:
        raise SystemExit(f"BLOCKED: require 3/3 validated SSE/SZSE/BSE smoke; got {len(ok)}/3 {sorted(exchanges)}")

    rows=[]
    for r in read(FROZEN):
        rows.append({
            "sample_id":r["sample_id"], "role":r["role"], "board":r["board"], "year":r["year"],
            "stock_code":r["stock_code"], "company_name":r["company_name"], "exchange":exchange_for(r),
            "disclosure_date":"", "source_url":"", "source_type":"", "download_status":"needs_resolution",
            "pdf_path":"", "sha256":"", "notes":"Stage 5B.5 frozen independent sample",
        })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fields=list(rows[0])
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w=csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
    print("Stage 5B.5 manifest written:", OUT.relative_to(ROOT))
    print("Total:",len(rows),"DEV:",sum(r["role"]=="DEV" for r in rows),"VAL:",sum(r["role"]=="VAL" for r in rows),"BLIND:",sum(r["role"]=="BLIND" for r in rows))

if __name__ == "__main__": main()
