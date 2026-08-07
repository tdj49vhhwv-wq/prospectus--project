import json

from evaluate_events import (
    CONTEXT_MAP,
    build_auto_events,
    build_gold_events,
    dates_compatible,
    match_events,
    parse_date,
)


def test_date_granularity_compatible():
    assert dates_compatible("2020-09-27", "2020-09-27") is True
    assert dates_compatible("2020-09-27", "2020-09-28") is False
    assert dates_compatible("2007-12", "2007-12-31") is True
    assert dates_compatible("2007-12", "2008-01-01") is False
    assert dates_compatible("2015", "2015-08-01") is True
    assert dates_compatible("2015", "2016-01-01") is False


def test_parse_date_missing_parts():
    assert parse_date("2007-12") == (2007, 12, 0)
    assert parse_date("") == (0, 0, 0)


def test_context_map_covers_pipeline_types():
    for context in ["设立", "增资", "整体变更", "增资及股权转让", "股权转让",
                    "资本公积转增", "吸收合并", "员工持股平台出资"]:
        assert context in CONTEXT_MAP


def test_gold_event_merges_investor_rows(tmp_path):
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir()
    rows = [
        {"record_type": "subscription_flow", "stock_code": "001282", "company_name": "三联锻造",
         "subscription_date": "2004-06-18", "event_context": "增资", "subscriber_name": "A",
         "evidence_text": "e1", "source_page": "PDF p1"},
        {"record_type": "subscription_flow", "stock_code": "001282", "company_name": "三联锻造",
         "subscription_date": "2004-06-18", "event_context": "增资", "subscriber_name": "B",
         "evidence_text": "e1", "source_page": "PDF p1"},
    ]
    with open(gold_dir / "subscription_flow_gold.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(gold_dir / "share_transfer_flow_gold.jsonl", "w", encoding="utf-8") as f:
        f.write("")
    events = build_gold_events(gold_dir)
    assert len(events) == 1
    assert events[0]["row_count"] == 2
    assert events[0]["type_code"] == "A"


def test_gold_share_transfer_maps_to_d(tmp_path):
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir()
    with open(gold_dir / "subscription_flow_gold.jsonl", "w", encoding="utf-8") as f:
        f.write("")
    rows = [{"record_type": "share_transfer_flow", "stock_code": "301581",
             "company_name": "黄山谷捷", "transfer_date": "2021-04-07",
             "transfer_type": "同一控制下转让", "transferor_name": "A",
             "transferee_name": "B", "evidence_text": "e", "source_page": "PDF p33"}]
    with open(gold_dir / "share_transfer_flow_gold.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    events = build_gold_events(gold_dir)
    assert len(events) == 1
    assert events[0]["type_code"] == "D"


def test_auto_event_dedupe(tmp_path):
    auto_dir = tmp_path / "auto"
    auto_dir.mkdir()
    rows = [
        {"stock_code": "001282", "subscription_date": "2004-06-18", "event_context": "增资",
         "subscriber_name": "A", "evidence_text": "e"},
        {"stock_code": "001282", "subscription_date": "2004-06-18", "event_context": "增资",
         "subscriber_name": "B", "evidence_text": "e"},
    ]
    with open(auto_dir / "001282_subscription_flow.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    events = build_auto_events(auto_dir)
    assert len(events) == 1


def test_one_to_one_greedy_no_double_match():
    gold = [
        {"stock_code": "001282", "date": "2004-06-18", "date_type": "day",
         "type_code": "A", "context": "增资", "company_name": "x", "row_count": 1},
        {"stock_code": "001282", "date": "2007-12", "date_type": "month",
         "type_code": "A", "context": "增资", "company_name": "x", "row_count": 1},
    ]
    auto = [
        {"stock_code": "001282", "date": "2007-12", "date_type": "month",
         "type_code": "A", "context": "增资", "company_name": "x", "row_count": 1},
        {"stock_code": "001282", "date": "2004-06-18", "date_type": "day",
         "type_code": "A", "context": "增资", "company_name": "x", "row_count": 1},
    ]
    gold_result, auto_result = match_events(gold, auto)
    assert sum(1 for r in gold_result.values() if r["status"] == "TP") == 2
    assert sum(1 for r in auto_result.values() if r["status"] == "TP") == 2


def test_global_auto_indexes_do_not_collide_across_companies():
    """两个公司各自匹配一条，结果索引必须落在各自的全局位置。"""
    gold = [
        {"stock_code": "001282", "date": "2004-06-18", "date_type": "day",
         "type_code": "E", "context": "设立", "company_name": "x", "row_count": 1},
        {"stock_code": "301563", "date": "2008-05-07", "date_type": "day",
         "type_code": "E", "context": "设立", "company_name": "y", "row_count": 1},
    ]
    auto = [
        {"stock_code": "001282", "date": "2004-06-18", "date_type": "day",
         "type_code": "E", "context": "设立", "company_name": "x", "row_count": 1},
        {"stock_code": "301563", "date": "2008-05-07", "date_type": "day",
         "type_code": "E", "context": "设立", "company_name": "y", "row_count": 1},
    ]
    gold_result, auto_result = match_events(gold, auto)
    assert sum(1 for r in gold_result.values() if r["status"] == "TP") == 2
    assert sum(1 for r in auto_result.values() if r["status"] == "TP") == 2
    assert auto_result[1]["status"] == "TP"
    assert auto_result[1]["matched_gold_id"] == 1
