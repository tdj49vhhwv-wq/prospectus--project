#!/usr/bin/env python3
"""Run the deterministic Week 8 Auto-vs-Gold evaluation pipeline."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from week8.evaluation.event_evaluator import (  # noqa: E402
    collapse_auto_rows_to_events,
    collapse_gold_rows_to_events,
    evaluate_events,
)
from week8.evaluation.investor_evaluator import evaluate_investors  # noqa: E402
from week8.evaluation.io import (  # noqa: E402
    load_aliases,
    load_jsonl,
    sha256_file,
    write_csv,
    write_json,
)
from week8.evaluation.normalize import normalize_date, normalize_number  # noqa: E402


DEFAULT_GOLD = PROJECT_ROOT / "week8/gold/subscription_flow_gold_v1.1.jsonl"
DEFAULT_DISPUTES = PROJECT_ROOT / "week8/gold/gold_disputes_v1.1.jsonl"
DEFAULT_ALIASES = PROJECT_ROOT / "week8/evaluation/investor_aliases.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "week8/results"


def _load_markdown_candidates() -> List[dict]:
    pipeline_dir = PROJECT_ROOT / "week6/pipeline"
    if str(pipeline_dir) not in sys.path:
        sys.path.insert(0, str(pipeline_dir))
    from markdown_source import make_located_data
    from run_md_pipeline import COMPANIES, extract_from_snippets

    rows = []
    for code, name in COMPANIES:
        located = make_located_data(code, name)
        if not located:
            raise RuntimeError(f"Markdown source unavailable: {code} {name}")
        rows.extend(extract_from_snippets(located["pevc_snippets"], code, name))
    return rows


def _error_rows(result, side_names=("auto_id", "gold_id")) -> List[dict]:
    rows = []
    for error_type, records, id_field in (
        ("FP", result.false_positives, side_names[0]),
        ("FN", result.false_negatives, side_names[1]),
    ):
        for record in records:
            rows.append(
                {
                    "error_type": error_type,
                    "record_id": record.get(id_field, record.get("event_id", "")),
                    "stock_code": record.get("stock_code", ""),
                    "date": record.get("subscription_date", record.get("date", "")),
                    "event_type": record.get("event_context", record.get("type", record.get("rule", ""))),
                    "investor_name": record.get(
                        "subscriber_name", record.get("investor_name", record.get("party", ""))
                    ),
                    "source_page": record.get("source_page", ""),
                    "evidence_text": record.get("evidence_text", ""),
                }
            )
    return sorted(rows, key=lambda row: (row["error_type"], row["stock_code"], str(row["record_id"])))


def _field_completeness(auto_rows: Iterable[dict]) -> List[dict]:
    rows = list(auto_rows)
    specs = (
        ("subscription_date", None),
        ("amount_subscribed", "万元"),
        ("shares_subscribed", "万股"),
        ("price_per_share", "元/股"),
    )
    output = []
    for field, unit in specs:
        statuses = Counter()
        for row in rows:
            result = (
                normalize_date(row.get(field))
                if unit is None
                else normalize_number(row.get(field), unit)
            )
            statuses[result.status] += 1
        total = len(rows)
        normalized = statuses["normalized"]
        output.append(
            {
                "field": field,
                "total": total,
                "normalized": normalized,
                "missing": statuses["missing"],
                "invalid": statuses["invalid"],
                "normalized_rate": round(normalized / total, 6) if total else None,
            }
        )
    return output


def _analysis_markdown(event_errors: List[dict], investor_errors: List[dict]) -> str:
    lines = [
        "# Week 8 严格误差样例",
        "",
        "以下项目按稳定ID排序，只展示前10条；完整错误保存在CSV。",
    ]
    for title, errors in (("事件级", event_errors), ("投资人级", investor_errors)):
        lines.extend(["", f"## {title}"])
        for error_type in ("FP", "FN"):
            lines.extend(["", f"### {error_type} Top 10", ""])
            selected = [row for row in errors if row["error_type"] == error_type][:10]
            if not selected:
                lines.append("无。")
                continue
            for row in selected:
                evidence = str(row["evidence_text"]).replace("\n", " ").strip()[:240]
                lines.append(
                    f"- `{row['record_id']}`｜{row['stock_code']}｜{row['date']}｜"
                    f"{row['event_type']}｜{row['investor_name']}｜{row['source_page']}：{evidence}"
                )
    return "\n".join(lines) + "\n"


def _summary_markdown(
    gold_rows,
    auto_rows,
    gold_events,
    auto_events,
    event_result,
    investor_result,
    completeness,
    source_gold_count,
    excluded_gold_count,
) -> str:
    event = event_result.metrics["overall"]
    investor = investor_result.metrics["overall"]
    return f"""# Week 8 严格基线总结

## 样本

- 开发集公司：{len({row.get('stock_code') for row in gold_rows})} 家；
- 原始Gold：{source_gold_count} 条；
- 暂时排除争议Gold：{excluded_gold_count} 条；
- Gold投资人明细：{len(gold_rows)} 条；
- Gold事件：{len(gold_events)} 个；
- Auto原始候选：{len(auto_rows)} 条；
- Auto事件候选：{len(auto_events)} 个。

## 严格指标

| 层级 | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| 事件级 | {event['tp']} | {event['fp']} | {event['fn']} | {event['precision']} | {event['recall']} | {event['f1']} |
| 投资人级 | {investor['tp']} | {investor['fp']} | {investor['fn']} | {investor['precision']} | {investor['recall']} | {investor['f1']} |

## 字段完整性

""" + "\n".join(
        f"- `{row['field']}`：{row['normalized']}/{row['total']}，标准化率 {row['normalized_rate']}"
        for row in completeness
    ) + "\n\n以上数字是严格Auto-vs-Gold结果，不以候选数量或规则覆盖率替代准确率。\n"


def run(
    gold_path: Path,
    auto_path: Path,
    output_dir: Path,
    aliases_path: Path,
    disputes_path: Path | None = None,
) -> dict:
    source_gold_rows = load_jsonl(gold_path)
    disputed_rows = load_jsonl(disputes_path) if disputes_path and disputes_path.exists() else []
    disputed_ids = {row.get("gold_id") for row in disputed_rows}
    gold_rows = [row for row in source_gold_rows if row.get("gold_id") not in disputed_ids]
    auto_rows = load_jsonl(auto_path) if auto_path else _load_markdown_candidates()
    aliases = load_aliases(aliases_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    gold_events = collapse_gold_rows_to_events(gold_rows)
    auto_events = collapse_auto_rows_to_events(auto_rows)
    event_result = evaluate_events(gold_events, auto_events)
    investor_result = evaluate_investors(gold_rows, auto_rows, aliases)
    event_errors = _error_rows(event_result)
    investor_errors = _error_rows(investor_result)
    completeness = _field_completeness(auto_rows)

    write_json(output_dir / "event_metrics.json", event_result.metrics)
    write_json(output_dir / "investor_metrics.json", investor_result.metrics)
    write_csv(
        output_dir / "event_matches.csv",
        event_result.matches,
        ["auto_id", "gold_id", "stock_code", "event_type", "date_match", "type_match"],
    )
    write_csv(
        output_dir / "event_errors.csv",
        event_errors,
        ["error_type", "record_id", "stock_code", "date", "event_type", "investor_name", "source_page", "evidence_text"],
    )
    write_csv(
        output_dir / "investor_matches.csv",
        investor_result.matches,
        ["auto_id", "gold_id", "stock_code", "event_type", "investor_name", "name_match", "field_status"],
    )
    write_csv(
        output_dir / "investor_errors.csv",
        investor_errors,
        ["error_type", "record_id", "stock_code", "date", "event_type", "investor_name", "source_page", "evidence_text"],
    )
    write_csv(
        output_dir / "field_completeness.csv",
        completeness,
        ["field", "total", "normalized", "missing", "invalid", "normalized_rate"],
    )
    (output_dir / "error_analysis.md").write_text(
        _analysis_markdown(event_errors, investor_errors), encoding="utf-8"
    )
    (output_dir / "week8_summary.md").write_text(
        _summary_markdown(
            gold_rows,
            auto_rows,
            gold_events,
            auto_events,
            event_result,
            investor_result,
            completeness,
            len(source_gold_rows),
            len(source_gold_rows) - len(gold_rows),
        ),
        encoding="utf-8",
    )
    manifest = {
        "gold_sha256": sha256_file(gold_path),
        "disputes_sha256": sha256_file(disputes_path) if disputes_path and disputes_path.exists() else None,
        "auto_sha256": sha256_file(auto_path) if auto_path else None,
        "auto_source": "jsonl" if auto_path else "week6_markdown_pipeline_in_memory",
        "source_gold_rows": len(source_gold_rows),
        "temporarily_excluded_gold_rows": len(source_gold_rows) - len(gold_rows),
        "gold_rows": len(gold_rows),
        "gold_events": len(gold_events),
        "auto_rows": len(auto_rows),
        "auto_events": len(auto_events),
        "aliases_sha256": sha256_file(aliases_path),
    }
    write_json(output_dir / "run_manifest.json", manifest)
    return manifest


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--disputes", type=Path, default=DEFAULT_DISPUTES)
    parser.add_argument("--auto", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--aliases", type=Path, default=DEFAULT_ALIASES)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    manifest = run(args.gold, args.auto, args.output_dir, args.aliases, args.disputes)
    print(
        f"Week 8 evaluation complete: Gold {manifest['gold_rows']} rows / "
        f"Auto {manifest['auto_rows']} rows -> {args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
