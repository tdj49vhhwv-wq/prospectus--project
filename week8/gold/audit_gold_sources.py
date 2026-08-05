#!/usr/bin/env python3
"""Audit whether inherited Gold evidence is traceable to current Markdown sources."""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GOLD = Path(__file__).with_name("subscription_flow_gold_v1.1.jsonl")
DEFAULT_CSV = Path(__file__).with_name("gold_source_audit.csv")
DEFAULT_REPORT = Path(__file__).with_name("gold_source_audit.md")


def _compact(value: object) -> str:
    return (
        re.sub(r"\s+", "", str(value or ""))
        .replace("（", "(")
        .replace("）", ")")
    )


def audit_row(row: dict, source_text: str, near_distance: int = 1500) -> dict:
    source = _compact(source_text)
    evidence = _compact(row.get("evidence_text"))
    name = _compact(row.get("subscriber_name"))
    year = str(row.get("subscription_date", ""))[:4]

    if evidence and evidence in source:
        status = "exact_evidence"
        action = "retain"
    else:
        name_positions = [match.start() for match in re.finditer(re.escape(name), source)] if name else []
        year_positions = [match.start() for match in re.finditer(re.escape(year), source)] if year else []
        near = any(abs(name_pos - year_pos) <= near_distance for name_pos in name_positions for year_pos in year_positions)
        if near:
            status = "name_year_near"
            action = "align_to_verbatim_source"
        elif name_positions:
            status = "name_only"
            action = "manual_source_review"
        else:
            status = "name_absent"
            action = "adjudicate_or_find_source"

    return {
        "gold_id": row.get("gold_id", ""),
        "stock_code": row.get("stock_code", ""),
        "subscription_date": row.get("subscription_date", ""),
        "subscriber_name": row.get("subscriber_name", ""),
        "claimed_source_page": row.get("source_page", ""),
        "review_status": row.get("review_status", ""),
        "traceability_status": status,
        "recommended_action": action,
        "evidence_text": row.get("evidence_text", ""),
    }


def audit_rows(rows: Iterable[dict], sources: Dict[str, str]) -> List[dict]:
    return [audit_row(row, sources.get(str(row.get("stock_code", "")), "")) for row in rows]


def load_default_sources() -> Dict[str, str]:
    pipeline_dir = PROJECT_ROOT / "week6/pipeline"
    if str(pipeline_dir) not in sys.path:
        sys.path.insert(0, str(pipeline_dir))
    from markdown_source import MD_FILES, get_md_dir

    source_dir = get_md_dir()
    return {
        code: "\n".join(
            (source_dir / filename).read_text(encoding="utf-8")
            for filename in filenames
            if (source_dir / filename).exists()
        )
        for code, filenames in MD_FILES.items()
    }


def main() -> int:
    rows = [json.loads(line) for line in DEFAULT_GOLD.read_text(encoding="utf-8").splitlines() if line.strip()]
    audited = audit_rows(rows, load_default_sources())
    with DEFAULT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(audited[0]),
            lineterminator="\n",
            quoting=csv.QUOTE_ALL,
        )
        writer.writeheader()
        writer.writerows(audited)

    counts = Counter(row["traceability_status"] for row in audited)
    disputed = [row for row in audited if row["traceability_status"] == "name_absent"]
    lines = [
        "# Gold v1.1 来源可追溯审计",
        "",
        "本审计只判断当前Markdown能否支持既有证据，不自动删除或改写Gold。",
        "",
        "## 结果",
        "",
    ]
    for status in ("exact_evidence", "name_year_near", "name_only", "name_absent"):
        lines.append(f"- `{status}`：{counts[status]} 条")
    lines.extend(["", "## 阻塞争议（当前文本中投资人名称不存在）", ""])
    for row in disputed:
        lines.append(
            f"- `{row['gold_id']}`｜{row['stock_code']}｜{row['subscription_date']}｜"
            f"{row['subscriber_name']}｜声称来源 {row['claimed_source_page']}"
        )
    DEFAULT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(dict(sorted(counts.items())), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
