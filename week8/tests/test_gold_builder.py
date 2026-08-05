import hashlib
import json
from pathlib import Path

import pytest

from week8.gold.build_gold_v1_1 import build_gold, load_jsonl


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_GOLD = PROJECT_ROOT / "week3/manual_gold/subscription_flow_gold.jsonl"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_build_gold_preserves_rows_evidence_and_source(tmp_path):
    source_hash = file_sha256(SOURCE_GOLD)
    source_rows = load_jsonl(SOURCE_GOLD)
    output = tmp_path / "gold.jsonl"

    summary = build_gold(SOURCE_GOLD, output)
    built_rows = load_jsonl(output)

    assert summary == {
        "gold_version": "1.1",
        "rows": 124,
        "companies": 8,
        "needs_review": 17,
    }
    assert len(built_rows) == len(source_rows) == 124
    assert [row["evidence_text"] for row in built_rows] == [
        row["evidence_text"] for row in source_rows
    ]
    assert file_sha256(SOURCE_GOLD) == source_hash


def test_build_gold_adds_unique_stable_ids_and_review_metadata(tmp_path):
    first_output = tmp_path / "first.jsonl"
    second_output = tmp_path / "second.jsonl"

    build_gold(SOURCE_GOLD, first_output)
    build_gold(SOURCE_GOLD, second_output)
    first = load_jsonl(first_output)
    second = load_jsonl(second_output)

    assert first == second
    assert len({row["gold_id"] for row in first}) == 124
    assert first[0]["gold_id"] == "GOLD-001282-2004-06-18-001"
    assert all(row["gold_version"] == "1.1" for row in first)
    assert {row["review_status"] for row in first} == {
        "inherited_manual_gold",
        "needs_review",
    }


def test_build_gold_rejects_missing_required_evidence(tmp_path):
    source = tmp_path / "broken.jsonl"
    source.write_text(
        json.dumps(
            {
                "stock_code": "001282",
                "subscription_date": "2020-01-01",
                "subscriber_name": "测试投资人",
                "event_context": "增资",
                "evidence_text": "",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="evidence_text"):
        build_gold(source, tmp_path / "out.jsonl")
