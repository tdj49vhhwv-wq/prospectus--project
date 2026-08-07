#!/usr/bin/env python3
"""把人工/LLM 补充行（如 VIE 轮次）合并进 validated 层，重跑两层评价。

合并结果写入 gitignore 的 week6/auto_output_md_all/，评价输出写入
week8/event_eval_all/ 与 week8/investor_eval_all/，便于与纯正则基线对比。
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SUPPLEMENTS = Path(__file__).resolve().parent / "supplements"
SRC_DIR = PROJECT_ROOT / "week6" / "auto_output_md" / "validated"
MERGED_DIR = PROJECT_ROOT / "week6" / "auto_output_md_all"


def main() -> None:
    merged_dir = MERGED_DIR / "validated"
    merged_dir.mkdir(parents=True, exist_ok=True)
    supplement_rows = []
    for path in sorted(SUPPLEMENTS.glob("*.jsonl")):
        with open(path, encoding="utf-8") as f:
            supplement_rows.extend(json.loads(line) for line in f if line.strip())

    for src in sorted(SRC_DIR.glob("*_subscription_flow.jsonl")):
        rows = [json.loads(line) for line in src.read_text().splitlines() if line.strip()]
        code = src.stem.split("_")[0]
        keys = {(r.get("subscription_date"), r.get("event_context"), r.get("subscriber_name"))
                for r in rows}
        for r in supplement_rows:
            if r.get("stock_code") != code:
                continue
            key = (r.get("subscription_date"), r.get("event_context"), r.get("subscriber_name"))
            if key in keys:
                continue
            rows.append(r)
            keys.add(key)
        (merged_dir / src.name).write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")

    eval_dir = PROJECT_ROOT / "week8" / "event_eval_all"
    inv_dir = PROJECT_ROOT / "week8" / "investor_eval_all"
    subprocess.run(["python3", "week8/evaluate_events.py", "--auto", str(merged_dir),
                    "--relax-gold-day-to-month", "--out", str(eval_dir)], cwd=PROJECT_ROOT, check=True)
    subprocess.run(["python3", "week8/evaluate_investors.py", "--auto", str(merged_dir),
                    "--relax-gold-day-to-month", "--out", str(inv_dir)], cwd=PROJECT_ROOT, check=True)

    event_sum = json.loads((eval_dir / "event_eval_summary.json").read_text())
    investor_sum = json.loads((inv_dir / "investor_eval_summary.json").read_text())
    print("supplement rows:", len(supplement_rows))
    print("event:", event_sum["overall"])
    print("investor:", investor_sum["overall"])


if __name__ == "__main__":
    main()
