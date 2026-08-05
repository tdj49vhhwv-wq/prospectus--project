import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "week6/pipeline"))

from run_md_pipeline import (
    extract_from_snippets,
    extract_investor_names,
    nearest_preceding_date,
)


def test_extract_investor_names_splits_joint_short_fund_names():
    assert extract_investor_names(["稳正景明、长泽创投"], "增资") == [
        "稳正景明",
        "长泽创投",
    ]


def test_extract_investor_names_rejects_procedural_phrases():
    assert extract_investor_names(
        ["全国股转公司就公司本次股票发行事项出具了"], "增资"
    ) == []


def test_known_joint_payment_sentence_returns_two_investors_only():
    snippet = {
        "pdf_page": 32,
        "text": (
            "截至2022年8月9日，公司已收到稳正景明、长泽创投缴纳的出资款"
            "2,374.40万元。本次股票发行新增股份于2022年9月1日挂牌。"
        ),
    }

    rows = extract_from_snippets([snippet], "920100", "三协电机")

    assert [row["subscriber_name"] for row in rows] == ["稳正景明", "长泽创投"]
    assert all(row["subscription_date"] == "2022-08-09" for row in rows)
    assert all(row["amount_subscribed"] == 2374.4 for row in rows)


def test_legal_entity_captured_before_contribution_is_preserved():
    assert extract_investor_names(
        ["深圳市测试创业投资合伙企业"], "增资"
    ) == ["深圳市测试创业投资合伙企业"]


def test_role_prefixes_are_removed_from_person_names():
    assert extract_investor_names(["其中原股东孙国奉"], "增资") == ["孙国奉"]


def test_nearest_preceding_date_uses_disclosed_context_only():
    text = "2014年5月，三联有限第二次增资。孙国奉出资1,995万元。2020年1月另行公告。"
    position = text.index("孙国奉")
    assert nearest_preceding_date(text, position) == "2014-05"


def test_nearest_preceding_date_never_reads_a_future_date():
    text = "孙国奉出资1,995万元。2020年1月另行公告。"
    assert nearest_preceding_date(text, text.index("孙国奉")) == ""


def test_investor_rows_inherit_the_nearest_disclosed_event_month():
    snippet = {
        "pdf_page": 1,
        "text": (
            "2014年5月，三联有限第二次增资3,000万元，"
            "孙国奉出资1,995万元，张松满出资1,005万元。"
        ),
    }
    rows = extract_from_snippets([snippet], "001282", "三联锻造")
    named_rows = [row for row in rows if row["subscriber_name"] != "（待识别）"]
    assert [(row["subscriber_name"], row["subscription_date"]) for row in named_rows] == [
        ("孙国奉", "2014-05"),
        ("张松满", "2014-05"),
    ]
