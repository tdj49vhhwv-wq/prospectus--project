import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluate_investors import (
    match_investor_rows,
    names_equal,
    names_fuzzy,
    norm_name,
    within_tol,
)


def test_norm_name_strips_spaces_and_brackets():
    assert norm_name(" 孙国奉 ") == "孙国奉"
    assert norm_name("芜湖高新同华创业投资合伙企业（有限合伙）") == "芜湖高新同华创业投资合伙企业(有限合伙)"


def test_within_tol():
    assert within_tol(1000.0, 1000.0) is True
    assert within_tol(1000.0, 1004.0) is True
    assert within_tol(1000.0, 1006.0) is False
    assert within_tol(None, 1000.0) is None
    assert within_tol(1000.0, None) is False


def test_names_equal_and_fuzzy():
    assert names_equal("孙国奉", "孙国奉") is True
    assert names_equal("孙国奉", "孙国敏") is False
    assert names_fuzzy("高新同华", "芜湖高新同华创业投资合伙企业(有限合伙)") is True


def test_match_investor_rows_no_double():
    gold = [
        {"subscriber_name": "孙国奉", "amount_subscribed": 175.0},
        {"subscriber_name": "孙国敏", "amount_subscribed": 162.5},
    ]
    auto = [
        {"subscriber_name": "孙国敏", "amount_subscribed": 162.5},
        {"subscriber_name": "孙国奉", "amount_subscribed": 175.0},
    ]
    pairs = match_investor_rows(gold, auto)
    assert len(pairs) == 2
    assert {gold[i]["subscriber_name"] for i, _ in pairs} == {"孙国奉", "孙国敏"}
    assert len({ai for _, ai in pairs}) == 2


def test_match_investor_rows_fuzzy():
    gold = [{"subscriber_name": "高新同华", "amount_subscribed": 1150.0}]
    auto = [{"subscriber_name": "芜湖高新同华创业投资合伙企业（有限合伙）", "amount_subscribed": 1150.0}]
    pairs = match_investor_rows(gold, auto)
    assert len(pairs) == 1
