#!/usr/bin/env python3
"""One-click reproduction of the Week 9 frozen-parser PE/VC investor metrics.

Reproduces the `pevc_investor_*` numbers in week9/final_dev_metrics.json:

  1. Runs the frozen Stage 7.1 parser (event_local_pevc.py) on the 8 Dev companies.
  2. Evaluates the resulting PE/VC investors against the gold standard via
     stage7/evaluate_pevc_investors_v2_fixed.py.

Usage:
    python3 week9/reproduce_freeze.py

Output:
    week9/freeze_repro/auto/   — frozen-parser raw output (per company)
    week9/freeze_repro/eval/   — pevc_eval_summary.json + pevc_eval_details.csv

Note: the frozen parser's runtime/ directory was never committed. This script
points the parser at the reconstructed stage71_frozen/runtime/markdown_source.py
(a copy of week6/pipeline/markdown_source.py) and sets PROSPECTUS_MD_DIR to the
repo's week1/review, so the parser can locate the markdown sources.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # repo root
WEEK9 = ROOT / "week9"
FROZEN = WEEK9 / "stage71_frozen"
PARSER = FROZEN / "event_local_pevc.py"
EVALUATOR = WEEK9 / "stage7" / "evaluate_pevc_investors_v2_fixed.py"
BASE = WEEK9 / "stage7" / "base_output" / "final"
MASTER = ROOT / "data" / "gold_standard" / "融资事件总表.jsonl"
GOLD_DETAILS = WEEK9 / "stage3" / "investor_eval" / "investor_eval_details.csv"
OUT = WEEK9 / "freeze_repro"


def run(cmd: list[str], **kwargs) -> None:
    print("+", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True, **kwargs)


def main() -> None:
    env = dict(os.environ)
    env["PROSPECTUS_MD_DIR"] = str(ROOT / "week1" / "review")

    auto_dir = OUT / "auto"
    auto_dir.mkdir(parents=True, exist_ok=True)

    # 1. frozen parser -> auto output
    run([sys.executable, str(PARSER), "--base", str(BASE), "--out", str(auto_dir)],
        env=env, cwd=str(FROZEN))

    # 2. PE/VC investor evaluator -> metrics
    run([sys.executable, str(EVALUATOR),
         "--gold-details", str(GOLD_DETAILS),
         "--auto-dir", str(auto_dir),
         "--master", str(MASTER),
         "--out", str(OUT / "eval")],
        cwd=str(WEEK9))

    summary = json.loads((OUT / "eval" / "pevc_eval_summary.json").read_text(encoding="utf-8"))
    print("\n" + json.dumps(summary, ensure_ascii=False, indent=2))
    f1 = summary.get("f1")
    gate = "PASS" if f1 is not None and f1 >= 0.90 else "FAIL"
    print(f"\nPE/VC Investor F1 >= 90% (freeze gate): {gate}")


if __name__ == "__main__":
    main()
