from week8.evaluation.event_evaluator import (
    collapse_auto_rows_to_events,
    collapse_gold_rows_to_events,
    evaluate_events,
)


def gold(code, date, event_type, gold_id="G1"):
    return {
        "gold_id": gold_id,
        "stock_code": code,
        "subscription_date": date,
        "event_context": event_type,
        "source_page": "PDF p1",
        "evidence_text": f"gold evidence {gold_id}",
    }


def auto(code, date, event_type, auto_id="A1"):
    return {
        "auto_id": auto_id,
        "stock_code": code,
        "subscription_date": date,
        "event_context": event_type,
        "source_page": "MD p1",
        "evidence_text": f"auto evidence {auto_id}",
    }


def test_exact_event_match_is_traceable():
    result = evaluate_events(
        [gold("001282", "2020-05-03", "增资")],
        [auto("001282", "2020-05-03", "增资")],
    )

    assert (result.tp, result.fp, result.fn) == (1, 0, 0)
    assert result.matches == [
        {
            "auto_id": "A1",
            "gold_id": "G1",
            "stock_code": "001282",
            "event_type": "增资",
            "date_match": "exact_day",
            "type_match": "exact",
        }
    ]
    assert result.metrics["overall"] == {
        "tp": 1,
        "fp": 0,
        "fn": 0,
        "precision": 1.0,
        "recall": 1.0,
        "f1": 1.0,
    }


def test_gold_month_accepts_auto_day_in_same_month_without_inventing_a_day():
    result = evaluate_events(
        [gold("001282", "2020-05", "增资")],
        [auto("001282", "2020-05-17", "增资")],
    )

    assert (result.tp, result.fp, result.fn) == (1, 0, 0)
    assert result.matches[0]["date_match"] == "gold_month"


def test_gold_day_does_not_accept_month_only_auto_date():
    result = evaluate_events(
        [gold("001282", "2020-05-17", "增资")],
        [auto("001282", "2020-05", "增资")],
    )
    assert (result.tp, result.fp, result.fn) == (0, 1, 1)


def test_wrong_company_or_incompatible_type_cannot_match():
    result = evaluate_events(
        [gold("001282", "2020-05", "设立")],
        [auto("301563", "2020-05-17", "设立", "A1"),
         auto("001282", "2020-05-17", "增资", "A2")],
    )
    assert (result.tp, result.fp, result.fn) == (0, 2, 1)


def test_composite_gold_event_accepts_one_component_type():
    result = evaluate_events(
        [gold("001282", "2020-05", "增资及股权转让")],
        [auto("001282", "2020-05-17", "增资")],
    )
    assert (result.tp, result.fp, result.fn) == (1, 0, 0)
    assert result.matches[0]["type_match"] == "composite_component"


def test_duplicate_auto_can_match_one_gold_only():
    result = evaluate_events(
        [gold("001282", "2020-05", "增资")],
        [
            auto("001282", "2020-05-03", "增资", "A1"),
            auto("001282", "2020-05-03", "增资", "A2"),
        ],
    )
    assert (result.tp, result.fp, result.fn) == (1, 1, 0)
    assert result.matches[0]["auto_id"] == "A1"
    assert result.false_positives[0]["auto_id"] == "A2"


def test_metrics_use_none_when_a_denominator_is_zero():
    result = evaluate_events([gold("001282", "2020-05", "增资")], [])
    assert result.metrics["overall"] == {
        "tp": 0,
        "fp": 0,
        "fn": 1,
        "precision": None,
        "recall": 0.0,
        "f1": None,
    }


def test_metrics_are_reported_by_company_and_event_type():
    result = evaluate_events(
        [
            gold("001282", "2020-05", "增资", "G1"),
            gold("301563", "2021-06", "设立", "G2"),
        ],
        [auto("001282", "2020-05-01", "增资", "A1")],
    )
    assert result.metrics["by_company"]["001282"]["recall"] == 1.0
    assert result.metrics["by_company"]["301563"]["recall"] == 0.0
    assert result.metrics["by_event_type"]["设立"]["fn"] == 1


def test_gold_investor_rows_from_one_disclosed_event_collapse_to_one_event():
    rows = [
        dict(gold("920100", "2022-08-09", "增资", "G1"), subscriber_name="稳正景明"),
        dict(gold("920100", "2022-08-09", "增资", "G2"), subscriber_name="长泽创投"),
    ]
    rows[1]["evidence_text"] = rows[0]["evidence_text"]
    rows[1]["source_page"] = rows[0]["source_page"]

    events = collapse_gold_rows_to_events(rows)

    assert len(events) == 1
    assert events[0]["member_ids"] == ["G1", "G2"]
    assert events[0]["investor_count"] == 2


def test_dated_auto_investor_candidates_collapse_by_company_date_and_type():
    rows = [
        dict(auto("920100", "2022-08-09", "增资", "A1"), subscriber_name="稳正景明"),
        dict(auto("920100", "2022-08-09", "增资", "A2"), subscriber_name="长泽创投"),
    ]
    rows[1]["evidence_text"] = "a second context for the same dated event"

    events = collapse_auto_rows_to_events(rows)

    assert len(events) == 1
    assert events[0]["member_ids"] == ["A1", "A2"]


def test_undated_auto_candidates_with_different_evidence_remain_separate_events():
    rows = [
        auto("920100", "", "增资", "A1"),
        auto("920100", "", "增资", "A2"),
    ]
    assert len(collapse_auto_rows_to_events(rows)) == 2
