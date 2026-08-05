from week8.gold.audit_gold_sources import audit_row


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
    assert result["recommended_action"] == "adjudicate_or_find_source"
