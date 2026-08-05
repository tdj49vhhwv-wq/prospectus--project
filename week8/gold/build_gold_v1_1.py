#!/usr/bin/env python3
"""Freeze the inherited manual Gold rows as an auditable v1.1 dataset."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = PROJECT_ROOT / "week3/manual_gold/subscription_flow_gold.jsonl"
DEFAULT_OUTPUT = Path(__file__).with_name("subscription_flow_gold_v1.1.jsonl")
GOLD_VERSION = "1.1"
REQUIRED_FIELDS = (
    "stock_code",
    "subscription_date",
    "subscriber_name",
    "event_context",
    "evidence_text",
    "source_page",
)
REVIEW_PATTERN = re.compile(r"confidence=low|推断|未逐轮披露|待从")


def load_jsonl(path: Path) -> List[dict]:
    with path.open(encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _validate_row(row: dict, line_number: int) -> None:
    for field in REQUIRED_FIELDS:
        value = row.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValueError(f"line {line_number}: missing required field {field}")


def _review_status(row: dict) -> str:
    searchable = " ".join(
        str(row.get(field, "")) for field in ("notes", "evidence_text")
    )
    return "needs_review" if REVIEW_PATTERN.search(searchable) else "inherited_manual_gold"


def build_gold(source: Path, output: Path) -> Dict[str, object]:
    rows = load_jsonl(source)
    counters: Counter = Counter()
    built_rows = []

    for line_number, original in enumerate(rows, 1):
        _validate_row(original, line_number)
        code = str(original["stock_code"])
        date = str(original["subscription_date"])
        counters[(code, date)] += 1
        built = dict(original)
        built.update(
            {
                "gold_id": f"GOLD-{code}-{date}-{counters[(code, date)]:03d}",
                "gold_version": GOLD_VERSION,
                "review_status": _review_status(original),
            }
        )
        built_rows.append(built)

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        for row in built_rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    return {
        "gold_version": GOLD_VERSION,
        "rows": len(built_rows),
        "companies": len({row["stock_code"] for row in built_rows}),
        "needs_review": sum(row["review_status"] == "needs_review" for row in built_rows),
    }


def main() -> int:
    summary = build_gold(DEFAULT_SOURCE, DEFAULT_OUTPUT)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
