#!/usr/bin/env python3
"""三种提取策略消融：仅正则 / 仅 LLM / 正则 + LLM。

默认运行不调 LLM；只有显式设置 DEEPSEEK_API_KEY 时才会发起 LLM 调用。
LLM 调用只处理 candidate 层的低置信度候选，并保存原始响应与费用日志。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ABLATION_DIR = Path(__file__).resolve().parent


def run_cmd(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=PROJECT_ROOT, check=True)


def collect_metrics() -> dict:
    event_sum = json.loads((PROJECT_ROOT / "week8" / "event_eval" / "event_eval_summary.json").read_text())
    investor_sum = json.loads((PROJECT_ROOT / "week8" / "investor_eval" / "investor_eval_summary.json").read_text())
    return {
        "event": event_sum["overall"],
        "investor": investor_sum["overall"],
        "match_options": event_sum["match_options"],
        "run_at": datetime.now().isoformat(timespec="seconds"),
    }


def arm_regex() -> None:
    run_cmd(["python3", "week8/evaluate_events.py", "--relax-gold-day-to-month"])
    run_cmd(["python3", "week8/evaluate_investors.py", "--relax-gold-day-to-month"])
    metrics = collect_metrics()
    (ABLATION_DIR / "metrics_regex.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2))
    print("regex arm:", metrics["event"], metrics["investor"])


def low_confidence_candidates(limit_per_company: int = 5) -> list[dict]:
    rows = []
    auto_dir = PROJECT_ROOT / "week6" / "auto_output_md" / "candidate"
    for path in sorted(auto_dir.glob("*_subscription_flow.jsonl")):
        company_rows = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                r = json.loads(line)
                if not r.get("subscription_date") or r.get("subscriber_name") == "（待识别）":
                    company_rows.append(r)
        rows.extend(company_rows[:limit_per_company])
    return rows


def arm_llm() -> None:
    if not os.environ.get("DEEPSEEK_API_KEY", "").strip():
        result = {"status": "skipped", "reason": "DEEPSEEK_API_KEY not set", "run_at": datetime.now().isoformat()}
        (ABLATION_DIR / "metrics_llm.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print("LLM arm skipped: DEEPSEEK_API_KEY not set")
        return

    import sys
    sys.path.insert(0, str(PROJECT_ROOT / "week6" / "pipeline"))
    from llm_extractor import LLMExtractor

    extractor = LLMExtractor()
    raw_dir = ABLATION_DIR / "raw_llm_responses"
    raw_dir.mkdir(exist_ok=True)
    cost_path = ABLATION_DIR / "llm_cost_log.csv"
    cost_initial = extractor.call_count
    with open(cost_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["run_at", "company", "page", "calls", "tokens_estimate", "cost_usd"])
        for r in low_confidence_candidates():
            before = extractor.call_count
            records = extractor.extract_subscriptions(
                r.get("evidence_text", "")[:4000],
                {"name": r.get("company_name", ""), "code": r.get("stock_code", "")},
            )
            calls = extractor.call_count - before
            raw = {"input": r, "output": records, "call_count": calls}
            safe_code = r.get("stock_code", "unknown")
            (raw_dir / f"{safe_code}_{r.get('subscription_date') or 'nodate'}.jsonl").write_text(
                json.dumps(raw, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            writer.writerow([datetime.now().isoformat(timespec="seconds"), safe_code,
                             r.get("source_page", ""), calls, "", ""])
    result = {"status": "done", "call_count": extractor.call_count - cost_initial}
    (ABLATION_DIR / "metrics_llm.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print("LLM arm done:", result)


def arm_regex_plus_llm() -> None:
    llm_path = ABLATION_DIR / "metrics_llm.json"
    if not llm_path.exists() or json.loads(llm_path.read_text()).get("status") != "done":
        result = {"status": "skipped", "reason": "LLM arm not run (DEEPSEEK_API_KEY required)"}
        (ABLATION_DIR / "metrics_regex_plus_llm.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print("regex+llm arm skipped: LLM arm not run")
        return
    metrics = collect_metrics()
    (ABLATION_DIR / "metrics_regex_plus_llm.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2))
    print("regex+llm arm:", metrics["event"], metrics["investor"])


def main() -> None:
    parser = argparse.ArgumentParser(description="三种提取策略消融")
    parser.add_argument("--arm", choices=["regex", "llm", "regex+llm"], default="regex")
    args = parser.parse_args()
    if args.arm == "regex":
        arm_regex()
    elif args.arm == "llm":
        arm_llm()
    else:
        arm_regex_plus_llm()


if __name__ == "__main__":
    main()
