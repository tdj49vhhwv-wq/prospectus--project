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
import re
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


def normalize_llm_date(value) -> str:
    if not value:
        return ""
    m = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月(?:\s*(\d{1,2})\s*日)?", str(value))
    if m:
        month = int(m.group(2))
        day = int(m.group(3)) if m.group(3) else None
        base = f"{m.group(1)}-{month:02d}"
        return f"{base}-{day:02d}" if day else base
    m = re.search(r"(\d{4})-(\d{1,2})(?:-(\d{1,2}))?", str(value))
    if m:
        month = int(m.group(2))
        base = f"{m.group(1)}-{month:02d}"
        if m.group(3):
            return f"{base}-{int(m.group(3)):02d}"
        return base
    return str(value).strip()


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
    normalized_rows = []
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
            for rec in records:
                rec = dict(rec)
                rec["stock_code"] = r.get("stock_code", "")
                rec["company_name"] = r.get("company_name", "")
                rec["subscription_date"] = normalize_llm_date(rec.get("subscription_date"))
                rec["source_page"] = r.get("source_page", "")
                rec["evidence_text"] = rec.get("evidence_text", r.get("evidence_text", ""))[:500]
                rec["validation_status"] = "validated" if rec["subscription_date"] else "candidate"
                rec["extraction_method"] = "llm_deepseek"
                rec["rule_id"] = "LLM01"
                normalized_rows.append(rec)
    (ABLATION_DIR / "llm_output.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in normalized_rows) + "\n",
        encoding="utf-8",
    )
    result = {"status": "done", "call_count": extractor.call_count - cost_initial}
    result["normalized_rows"] = len(normalized_rows)
    result["dated_rows"] = sum(1 for r in normalized_rows if r["subscription_date"])
    (ABLATION_DIR / "metrics_llm.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print("LLM arm done:", result)


def arm_regex_plus_llm() -> None:
    llm_path = ABLATION_DIR / "metrics_llm.json"
    if not llm_path.exists() or json.loads(llm_path.read_text()).get("status") != "done":
        result = {"status": "skipped", "reason": "LLM arm not run (DEEPSEEK_API_KEY required)"}
        (ABLATION_DIR / "metrics_regex_plus_llm.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print("regex+llm arm skipped: LLM arm not run")
        return
    llm_rows = [json.loads(line) for line in (ABLATION_DIR / "llm_output.jsonl").read_text().splitlines() if line.strip()]
    dated_rows = [r for r in llm_rows if r.get("subscription_date")]
    merged_dir = PROJECT_ROOT / "week6" / "auto_output_md_llm"
    merged_dir.mkdir(exist_ok=True)
    auto_dir = PROJECT_ROOT / "week6" / "auto_output_md" / "validated"
    for path in sorted(auto_dir.glob("*_subscription_flow.jsonl")):
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        code = path.stem.split("_")[0]
        keys = {(r.get("subscription_date"), r.get("event_context"), r.get("subscriber_name")) for r in rows}
        month_keys = {(r.get("subscription_date", "")[:7], r.get("event_context")) for r in rows}
        for r in dated_rows:
            if r.get("stock_code") != code:
                continue
            # LLM 行若与 validated 同月同类（如工商变更日重复披露），跳过
            if (r.get("subscription_date", "")[:7], r.get("event_context")) in month_keys:
                continue
            key = (r.get("subscription_date"), r.get("event_context"), r.get("subscriber_name"))
            if key in keys:
                continue
            rows.append(r)
            keys.add(key)
        (merged_dir / path.name).write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")

    merged_eval = ABLATION_DIR / "merged_eval"
    run_cmd(["python3", "week8/evaluate_events.py", "--auto", str(merged_dir),
             "--relax-gold-day-to-month", "--out", str(merged_eval / "event")])
    run_cmd(["python3", "week8/evaluate_investors.py", "--auto", str(merged_dir),
             "--relax-gold-day-to-month", "--out", str(merged_eval / "investor")])
    event_sum = json.loads((merged_eval / "event" / "event_eval_summary.json").read_text())
    investor_sum = json.loads((merged_eval / "investor" / "investor_eval_summary.json").read_text())
    metrics = {
        "event": event_sum["overall"],
        "investor": investor_sum["overall"],
        "match_options": event_sum["match_options"],
        "merged_rows": len(dated_rows),
        "run_at": datetime.now().isoformat(timespec="seconds"),
    }
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
