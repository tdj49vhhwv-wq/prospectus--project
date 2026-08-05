import json

from week8.gold import audit_gold_sources


audit_row = audit_gold_sources.audit_row


def gold(evidence="投资人甲于2020年5月完成增资。", name="投资人甲", date="2020-05"):
    return {
        "gold_id": "G1",
        "stock_code": "001282",
        "subscription_date": date,
        "subscriber_name": name,
        "evidence_text": evidence,
        "source_page": "PDF p1",
    }


def test_audit_accepts_only_verbatim_normalized_evidence_as_exact():
    result = audit_row(gold(), "前文\n投资人甲 于 2020年5月 完成增资。\n后文")
    assert result["traceability_status"] == "exact_evidence"
    assert result["recommended_action"] == "retain"


def test_audit_marks_name_and_year_nearby_as_manual_alignment_not_exact():
    result = audit_row(
        gold(evidence="人工概括的另一句话"),
        "2020年5月，公司向投资人甲发行股份。",
    )
    assert result["traceability_status"] == "name_year_near"
    assert result["recommended_action"] == "align_to_verbatim_source"


def test_audit_marks_absent_investor_as_blocking_dispute():
    result = audit_row(gold(name="不存在的投资人"), "2020年5月，公司完成增资。")
    assert result["traceability_status"] == "name_absent"
    assert result["recommended_action"] == "temporarily_exclude_pending_source"


def test_partition_temporarily_excludes_name_absent_without_deleting_source_gold():
    rows = [
        dict(gold(name="可追溯投资人"), gold_id="G1"),
        dict(gold(name="缺失投资人"), gold_id="G2"),
    ]
    audited = [
        dict(audit_row(rows[0], "可追溯投资人于2020年5月完成增资。")),
        dict(audit_row(rows[1], "2020年5月，公司完成增资。")),
    ]

    evaluable, disputes = audit_gold_sources.partition_rows(rows, audited)

    assert [row["gold_id"] for row in evaluable] == ["G1"]
    assert [row["gold_id"] for row in disputes] == ["G2"]
    assert disputes[0]["adjudication_status"] == "temporarily_excluded_pending_source"
    assert disputes[0]["traceability_status"] == "name_absent"
    assert len(evaluable) + len(disputes) == len(rows)


def test_write_partition_outputs_keeps_evaluable_and_disputed_rows_separate(tmp_path):
    rows = [
        dict(gold(name="可追溯投资人"), gold_id="G1"),
        dict(gold(name="缺失投资人"), gold_id="G2"),
    ]
    audited = [
        audit_row(rows[0], "可追溯投资人于2020年5月完成增资。"),
        audit_row(rows[1], "2020年5月，公司完成增资。"),
    ]
    evaluable_path = tmp_path / "evaluable.jsonl"
    disputes_path = tmp_path / "disputes.jsonl"

    counts = audit_gold_sources.write_partition_outputs(
        rows, audited, evaluable_path, disputes_path
    )

    evaluable = [json.loads(line) for line in evaluable_path.read_text().splitlines()]
    disputes = [json.loads(line) for line in disputes_path.read_text().splitlines()]
    assert counts == {"source_gold": 2, "evaluable": 1, "temporarily_excluded": 1}
    assert [row["gold_id"] for row in evaluable] == ["G1"]
    assert [row["gold_id"] for row in disputes] == ["G2"]
