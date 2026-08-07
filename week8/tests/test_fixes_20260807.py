import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "week6" / "pipeline"))

from run_md_pipeline import extract_from_snippets, is_valid_investor_name


def test_valid_investor_name_filters_non_entities():
    for name in ["法定代表人", "注册地址", "合计", "截至", "注册资本", "（待识别）", "123"]:
        assert is_valid_investor_name(name) is False, name
    for name in ["高新同华", "黄学英", "深圳云汉电子有限公司", "QM101 Limited"]:
        assert is_valid_investor_name(name) is True, name


def test_setup_pattern_matches_issuer_profile():
    rows = extract_from_snippets(
        [{"text": "有限公司成立日期 2004 年6 月18 日，孙国奉 认缴 175 万元", "pdf_page": 1}],
        "001282", "三联锻造")
    setups = [r for r in rows if r["event_context"] == "设立"]
    assert len(setups) == 1
    assert setups[0]["subscription_date"] == "2004-06-18"
    assert setups[0]["validation_status"] == "validated"


def test_setup_pattern_rejects_offshore_board_and_partnership():
    text = ("美国日升成立于2003年7月21日，注册地址为美国亚利桑那州。"
            "股份公司第一届董事会成立于2021 年8 月25 日。"
            "某合伙企业成立日期 2015 年1 月9 日，出资总额 2,400 万元。")
    rows = extract_from_snippets([{"text": text, "pdf_page": 1}], "603418", "友升股份")
    assert all(r["event_context"] != "设立" for r in rows)


def test_missing_date_rows_stay_in_candidate_layer():
    rows = extract_from_snippets(
        [{"text": "孙国奉以机器设备出资175万元，占注册资本35%", "pdf_page": 1}],
        "001282", "三联锻造")
    assert rows
    assert all(r["validation_status"] == "candidate" for r in rows)
