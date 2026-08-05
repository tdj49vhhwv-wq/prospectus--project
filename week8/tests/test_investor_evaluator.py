from week8.evaluation.investor_evaluator import evaluate_investors


ALIASES = {
    "稳正景明": "深圳市稳正景明创业投资企业(有限合伙)",
}


def gold_row(name, gold_id="G1", amount=None, shares=None, price=None):
    return {
        "gold_id": gold_id,
        "stock_code": "920100",
        "subscription_date": "2022-08-09",
        "event_context": "增资",
        "subscriber_name": name,
        "amount_subscribed": amount,
        "shares_subscribed": shares,
        "price_per_share": price,
        "source_page": "PDF p32",
        "evidence_text": f"gold evidence {gold_id}",
    }


def auto_row(name, auto_id="A1", amount=None, shares=None, price=None):
    return {
        "auto_id": auto_id,
        "stock_code": "920100",
        "subscription_date": "2022-08-09",
        "event_context": "增资",
        "subscriber_name": name,
        "amount_subscribed": amount,
        "shares_subscribed": shares,
        "price_per_share": price,
        "source_page": "MD p32",
        "evidence_text": f"auto evidence {auto_id}",
    }


def test_alias_match_is_a_traceable_investor_tp():
    result = evaluate_investors(
        [gold_row("深圳市稳正景明创业投资企业（有限合伙）")],
        [auto_row("稳正景明")],
        ALIASES,
    )
    assert (result.tp, result.fp, result.fn) == (1, 0, 0)
    assert result.matches[0]["name_match"] == "normalized_exact"
    assert result.matches[0]["auto_id"] == "A1"
    assert result.matches[0]["gold_id"] == "G1"


def test_two_investors_in_one_event_are_scored_separately():
    result = evaluate_investors(
        [gold_row("稳正景明", "G1"), gold_row("长泽创投", "G2")],
        [auto_row("稳正景明", "A1")],
        {},
    )
    assert (result.tp, result.fp, result.fn) == (1, 0, 1)
    assert result.false_negatives[0]["subscriber_name"] == "长泽创投"


def test_non_investor_entity_is_a_false_positive_not_a_fuzzy_match():
    result = evaluate_investors(
        [gold_row("稳正景明")],
        [auto_row("深圳市稳正资产管理有限公司")],
        {},
    )
    assert (result.tp, result.fp, result.fn) == (0, 1, 1)


def test_duplicate_auto_investor_can_match_only_one_gold_row():
    result = evaluate_investors(
        [gold_row("稳正景明")],
        [auto_row("稳正景明", "A1"), auto_row("稳正景明", "A2")],
        {},
    )
    assert (result.tp, result.fp, result.fn) == (1, 1, 0)
    assert result.matches[0]["auto_id"] == "A1"


def test_numeric_fields_use_relative_tolerance_after_identity_match():
    result = evaluate_investors(
        [gold_row("稳正景明", amount=100.0, shares=50.0, price=4.48)],
        [auto_row("稳正景明", amount=100.4, shares=50.0, price=4.50)],
        {},
    )
    fields = result.matches[0]["field_status"]
    assert fields == {
        "amount_subscribed": "match",
        "shares_subscribed": "match",
        "price_per_share": "match",
    }


def test_numeric_field_status_distinguishes_missing_and_not_disclosed():
    result = evaluate_investors(
        [gold_row("稳正景明", amount=100.0, shares=None, price=None)],
        [auto_row("稳正景明", amount=None, shares=50.0, price=None)],
        {},
    )
    assert result.matches[0]["field_status"] == {
        "amount_subscribed": "auto_missing",
        "shares_subscribed": "gold_not_disclosed",
        "price_per_share": "gold_not_disclosed",
    }
    assert result.field_metrics["amount_subscribed"]["auto_missing"] == 1


def test_wrong_event_date_prevents_investor_match():
    auto_record = auto_row("稳正景明")
    auto_record["subscription_date"] = "2022-09-09"
    result = evaluate_investors([gold_row("稳正景明")], [auto_record], {})
    assert (result.tp, result.fp, result.fn) == (0, 1, 1)
