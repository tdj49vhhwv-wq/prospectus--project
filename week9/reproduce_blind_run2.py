#!/usr/bin/env python3
"""One-click reproduction of Post-Blind Revision (Stage 7.2) Blind Run #2.

Pipeline:
  1. (re)generate base events for the two blind companies 688795/688802
     via week6/pipeline/run_md_pipeline.py (--no-db).
  2. Run the Stage 7.2 parser (stage72_postblind/event_local_pevc.py) on those
     base events -> per-company *_subscription_flow.jsonl.
  3. Convert the JSONL to the same schema as blind_run1's PE/VC rows CSV.
  4. Evaluate against the frozen blind_gold.csv -> blind_run2 metrics.

The frozen stage71_frozen/ and blind_run1/ are never touched.

Usage:
    python3 week9/reproduce_blind_run2.py
"""
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEEK9 = ROOT / "week9"
PARSER = WEEK9 / "stage72_postblind" / "event_local_pevc.py"
BASE_PIPELINE = ROOT / "week6" / "pipeline" / "run_md_pipeline.py"
EVALUATOR = WEEK9 / "evaluate_blind_run2.py"

BLIND_CODES = ["688795", "688802"]
BASE_DIR = WEEK9 / "stage72_postblind" / "base_output" / "final"
AUTO_DIR = WEEK9 / "stage72_postblind" / "auto_output" / "final"
OUT_DIR = WEEK9 / "blind_run2"

COLS = ["stock_code", "subscription_date", "event_context", "subscriber_name",
        "amount_subscribed", "shares_subscribed", "price_per_share",
        "source", "evidence_text"]


def run(cmd, env, cwd=None):
    print("+", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True, env=env, cwd=cwd)


def main() -> None:
    env = dict(os.environ)
    env["PROSPECTUS_MD_DIR"] = str(ROOT / "week1" / "review")

    # 1. base events (idempotent)
    run([sys.executable, str(BASE_PIPELINE),
         "--companies", *BLIND_CODES,
         "--out", str(WEEK9 / "stage72_postblind" / "base_output"),
         "--no-db"], env=env, cwd=str(ROOT / "week6" / "pipeline"))

    # 2. Stage 7.2 parser
    AUTO_DIR.parent.mkdir(parents=True, exist_ok=True)
    run([sys.executable, str(PARSER), "--base", str(BASE_DIR), "--out", str(AUTO_DIR)],
        env=env, cwd=str(WEEK9 / "stage72_postblind"))

    # 3. JSONL -> CSV
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUT_DIR / "week9_blind_run2_pevc_rows.csv"
    rows = []
    for code in BLIND_CODES:
        p = AUTO_DIR / f"{code}_subscription_flow.jsonl"
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            rows.append({c: r.get(c) for c in COLS})
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    # 4. evaluate
    run([sys.executable, str(EVALUATOR)], env=env, cwd=str(WEEK9))


if __name__ == "__main__":
    main()
