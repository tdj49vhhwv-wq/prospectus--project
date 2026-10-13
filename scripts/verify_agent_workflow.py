#!/usr/bin/env python3
"""Exercise offline workflows without rewriting historical research outputs."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = Path(tempfile.mkdtemp(prefix="prospectus-verification-"))
    print(f"Verification artifacts: {output}", flush=True)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "week8")
    env["PROSPECTUS_MD_DIR"] = str(ROOT / "week1/review")
    # This verifier is deliberately offline, even on machines with DB bindings.
    for name in ("DB_HOST", "DB_USER", "DB_PASSWORD", "DB_PORT", "DB_NAME"):
        env.pop(name, None)
    failures = []

    def run(name, args, cwd=ROOT):
        print(f"\n== {name} ==", flush=True)
        result = subprocess.run([sys.executable, *map(str, args)], cwd=cwd, env=env)
        if result.returncode:
            failures.append(f"{name}: exit {result.returncode}")
        return result.returncode == 0

    run("Existing tests", ["-m", "pytest", "week6/tests", "week8/tests", "-q", "-p", "no:cacheprovider"])
    if run("Eight-company Markdown extraction", ["pipeline/run_md_pipeline.py", "--no-db", "--out", output / "md"], ROOT / "week6"):
        expected = {"001282", "301563", "301581", "603418", "688758", "688775", "920100", "920116"}
        files = list((output / "md/candidate").glob("*.jsonl"))
        # Check actual generated records rather than the command's exit status alone.
        rows = [json.loads(line) for path in files for line in path.read_text().splitlines() if line.strip()]
        found = {row["stock_code"] for row in rows}
        if found != expected:
            failures.append(f"Markdown company coverage: expected {sorted(expected)}, got {sorted(found)}")
        print(f"Markdown: {len(rows)} candidates across {len(found)} companies", flush=True)
    frozen_ok = run("Frozen parser", ["event_local_pevc.py", "--base", ROOT / "week9/stage7/base_output/final", "--out", output / "frozen-auto"], ROOT / "week9/stage71_frozen")
    if frozen_ok and run("Frozen investor evaluation", [ROOT / "week9/stage7/evaluate_pevc_investors_v2_fixed.py", "--gold-details", ROOT / "week9/stage3/investor_eval/investor_eval_details.csv", "--auto-dir", output / "frozen-auto", "--master", ROOT / "data/gold_standard/融资事件总表.jsonl", "--out", output / "frozen-eval"]):
        summary = json.loads((output / "frozen-eval/pevc_eval_summary.json").read_text())
        if summary["gold"] != 42 or summary["matched"] != 42 or summary["auto"] != 45:
            failures.append(f"Frozen baseline changed: {summary}")
        print(f"Frozen metrics: {summary}", flush=True)
    if failures:
        print("\nFAILED:\n" + "\n".join(failures), flush=True)
        return 1
    print("\nAll offline checks passed.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
