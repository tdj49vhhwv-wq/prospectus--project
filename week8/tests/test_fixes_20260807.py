import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "week6" / "pipeline"))

from run_md_pipeline import extract_from_snippets, is_valid_investor_name
from evaluate_events import build_auto_events, dates_compatible


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


def test_compound_event_pattern_flowchart():
    text = 'A["2009年12月，有限公司第一次股权转让及增资，注册资本增至100万元"]'
    rows = extract_from_snippets([{"text": text, "pdf_page": 1}], "301563", "云汉芯城")
    cs = [r for r in rows if r["event_context"] == "增资及股权转让"]
    assert cs and cs[0]["subscription_date"] == "2009-12"


def test_zero_price_transfer_uses_registration_date():
    text = ("2020 年12 月30 日，批复同意昆山谷捷将其所持谷捷有限78%的股权以零对价转让给黄山供销集团。"
            "2021 年4 月7 日，谷捷有限取得了黄山市徽州区市场监督管理局为其换发的营业执照。")
    rows = extract_from_snippets([{"text": text, "pdf_page": 1}], "301581", "黄山谷捷")
    ds = [r for r in rows if r["event_context"] == "股权转让"]
    assert ds and ds[0]["subscription_date"] == "2021-04-07"


def test_share_issue_pattern():
    text = "2021 年11 月，赛分科技增发股份4,243,901 股，新增股份由新增股东源峰磐赛认购。"
    rows = extract_from_snippets([{"text": text, "pdf_page": 1}], "688758", "赛分科技")
    assert any(r["event_context"] == "增资" for r in rows)


def test_agent_transfer_pattern():
    text = ("2017 年10 月9 日，星图测控有限的股东会作出决议，同意：罗永红将其持有的星图测控有限20%股权转让予牛威。"
            "星图测控有限于2017 年10 月25 日就上述股权转让办理了工商变更登记手续。")
    rows = extract_from_snippets([{"text": text, "pdf_page": 1}], "920116", "星图测控")
    ds = [r for r in rows if r["event_context"] == "股权转让"]
    assert ds and all(r["subscription_date"] == "2017-10-25" for r in ds)


def test_evaluator_d_rows_kept_separate(tmp_path):
    auto_dir = tmp_path / "auto"
    auto_dir.mkdir()
    rows = [
        {"stock_code": "301581", "subscription_date": "2021-04-07", "event_context": "股权转让",
         "subscriber_name": "黄山供销集团", "evidence_text": "e"},
        {"stock_code": "301581", "subscription_date": "2021-04-07", "event_context": "股权转让",
         "subscriber_name": "张俊武", "evidence_text": "e"},
    ]
    with open(auto_dir / "301581_subscription_flow.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    events = build_auto_events(auto_dir)
    assert len(events) == 2


def test_relax_gold_day_to_month():
    assert dates_compatible("2020-09-27", "2020-09", relax_gold_day_to_month=True) is True
    assert dates_compatible("2020-09-27", "2020-10", relax_gold_day_to_month=True) is False
    assert dates_compatible("2020-09-27", "2020-09", relax_gold_day_to_month=False) is False
