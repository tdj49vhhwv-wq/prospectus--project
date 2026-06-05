#!/usr/bin/env python3
"""
==========================================================================
 JSON输出校验脚本
 检查: Schema完整性 / 字段类型 / 证据文本 / 来源位置 / 置信度
==========================================================================
"""
import json
import sys
import csv
from pathlib import Path
from datetime import datetime

BASE_DIR = Path("/Users/zhaobingqing/Documents/GitHub/prospectus-pevc-project")
JSON_DIR = BASE_DIR / "outputs" / "week1_sample_json"
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

REQUIRED_EVENT_FIELDS = [
    "event_order", "event_date", "date_type", "event_type",
    "disclosed_round", "inferred_round", "round_inference_basis",
    "total_investment_amount", "currency", "share_price",
    "pre_money_valuation", "post_money_valuation", "valuation_basis",
    "investors", "source_section", "source_page", "evidence_text", "confidence"
]
REQUIRED_INVESTOR_FIELDS = [
    "investor_original_name", "investor_short_name", "investor_type",
    "is_pevc", "investment_amount", "shares_acquired",
    "shareholding_ratio_after_event", "exit_status_before_ipo"
]
VALID_DATE_TYPES = ["协议签署日", "工商变更日", "股东会决议日", "未说明"]
VALID_EVENT_TYPES = ["增资", "股权转让", "增资及股权转让", "其他"]
VALID_INVESTOR_TYPES = ["VC", "PE", "产业资本", "自然人", "员工持股平台", "政府基金", "其他", "无法判断"]
VALID_CONFIDENCE = ["high", "medium", "low"]


def validate_json_file(filepath):
    """校验单个JSON文件"""
    results = []
    company = filepath.stem.replace("_融资历史_结构化", "")
    try:
        with open(filepath) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return [{"company": company, "status": "FAIL", "issue": f"JSON解析失败: {e}"}]

    c = data.get("company", {})
    events = c.get("financing_events", [])

    for i, e in enumerate(events):
        prefix = f"{company}/event{i+1}"

        # 检查字段完整性
        missing = [f for f in REQUIRED_EVENT_FIELDS if f not in e]
        for m in missing:
            results.append({"company": company, "event": i+1, "status": "FAIL",
                           "field": m, "issue": "字段缺失"})

        # 检查date_type枚举
        if e.get("date_type") not in VALID_DATE_TYPES:
            results.append({"company": company, "event": i+1, "status": "WARN",
                           "field": "date_type", "issue": f"非标准值: {e.get('date_type')}"})

        # 检查event_type枚举
        if e.get("event_type") not in VALID_EVENT_TYPES:
            results.append({"company": company, "event": i+1, "status": "WARN",
                           "field": "event_type", "issue": f"非标准值: {e.get('event_type')}"})

        # 检查confidence枚举
        if e.get("confidence") not in VALID_CONFIDENCE:
            results.append({"company": company, "event": i+1, "status": "WARN",
                           "field": "confidence", "issue": f"非标准值: {e.get('confidence')}"})

        # 检查证据文本长度
        evidence = e.get("evidence_text", "")
        if len(evidence) < 50:
            results.append({"company": company, "event": i+1, "status": "WARN",
                           "field": "evidence_text", "issue": f"证据文本过短({len(evidence)}字)"})

        # 检查来源信息
        if not e.get("source_section"):
            results.append({"company": company, "event": i+1, "status": "WARN",
                           "field": "source_section", "issue": "来源章节为空"})
        if not e.get("source_page"):
            results.append({"company": company, "event": i+1, "status": "WARN",
                           "field": "source_page", "issue": "来源页为空"})

        # 检查investors
        investors = e.get("investors", [])
        if not investors:
            results.append({"company": company, "event": i+1, "status": "WARN",
                           "field": "investors", "issue": "投资人列表为空"})
        for j, inv in enumerate(investors):
            inv_missing = [f for f in REQUIRED_INVESTOR_FIELDS if f not in inv]
            for m in inv_missing:
                results.append({"company": company, "event": i+1, "investor": j+1,
                               "status": "FAIL", "field": m, "issue": "字段缺失"})
            if inv.get("investor_type") not in VALID_INVESTOR_TYPES:
                results.append({"company": company, "event": i+1, "investor": j+1,
                               "status": "WARN", "field": "investor_type",
                               "issue": f"非标准值: {inv.get('investor_type')}"})

    if not results:
        results.append({"company": company, "status": "PASS", "events": len(events),
                       "issue": "全部字段通过校验"})

    return results


def main():
    print("=" * 50)
    print("JSON Schema 校验")
    print("=" * 50)

    all_results = []
    for f in sorted(JSON_DIR.glob("*_结构化.json")):
        r = validate_json_file(f)
        all_results.extend(r)
        company = f.stem.replace("_融资历史_结构化", "")
        fails = [x for x in r if x["status"] == "FAIL"]
        warns = [x for x in r if x["status"] == "WARN"]
        passes = [x for x in r if x["status"] == "PASS"]
        status = "FAIL" if fails else "PASS"
        print(f"  {status}: {company} (FAIL={len(fails)} WARN={len(warns)})")

    # 保存校验报告
    report_path = LOG_DIR / f"validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    # 写入CSV日志
    csv_path = LOG_DIR / "validation_log.csv"
    with open(csv_path, "a", newline="") as f:
        writer = csv.writer(f)
        for r in all_results:
            if r.get("status") == "PASS":
                writer.writerow([
                    datetime.now().isoformat(), "", r["company"],
                    "", r.get("events", ""), r["status"], "18/18",
                    "✓", "✓", r["status"], r["issue"]
                ])

    print(f"\n报告: {report_path.name}")
    total_fail = len([x for x in all_results if x["status"] == "FAIL"])
    total_warn = len([x for x in all_results if x["status"] == "WARN"])
    print(f"总计: FAIL={total_fail} WARN={total_warn}")
    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
