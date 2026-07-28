#!/usr/bin/env python3
"""
JSON输出校验脚本
检查: 字段完整性 / 事件日期合理性 / 投资人提取 / evidence来源可回源性 / 时间线一致性
"""
import json
import csv
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import OUTPUTS_DIR, LOG_DIR, REQUIRED_EVENT_FIELDS, REQUIRED_INVESTOR_FIELDS, PROJECT_ROOT
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 新 Schema: financing_events 在顶层
REQUIRED_TOP_FIELDS = [
    "company", "financing_events"
]
# 合法事件类型
VALID_EVENT_TYPES = ["增资", "股权转让", "整体变更", "吸收合并", "设立", "改制", "VIE搭建", "VIE拆除", "增资及股权转让", "其他"]

# evidence_text 中的概括性语言模式（应为原文片段，不应包含概括性开头）
SUMMARY_PATTERNS = [
    "招股书显示", "招股书披露", "根据招股书", "据招股书",
    "招股书说明", "招股书记载", "公告显示", "报告期内",
]


def validate_company(json_path):
    """校验单家公司JSON，返回 (overall, issues, details)"""
    company_key = json_path.parent.name
    issues = []
    details = {}

    with open(json_path) as f:
        data = json.load(f)

    # 1. 顶层字段检查
    missing_top = [f for f in REQUIRED_TOP_FIELDS if f not in data]
    if missing_top:
        issues.append(f"缺失顶层字段: {missing_top}")
    details["top_fields_ok"] = len(missing_top) == 0

    # 2. company 信息检查
    company_info = data.get("company", {})
    details["has_company_name"] = bool(company_info.get("company_name"))
    details["has_stock_code"] = bool(company_info.get("stock_code"))

    # 3. 融资事件检查 (顶层)
    events = data.get("financing_events", [])
    # 兼容旧格式
    if not events:
        events = company_info.get("financing_events", [])
        if events:
            issues.append("financing_events 在 company 对象内（旧格式），应提升到顶层")

    details["event_count"] = len(events)

    event_issues = 0
    evidence_issues = 0
    for i, e in enumerate(events):
        # 字段完整性
        missing = [f for f in REQUIRED_EVENT_FIELDS if f not in e or e[f] is None]
        for m in missing:
            # event_date 是必需字段
            if m in ("event_date", "event_type", "evidence_text", "confidence"):
                event_issues += 1
                issues.append(f"event[{i}] 缺失关键字段: {m}")

        etype = e.get("event_type", "")
        if etype and etype not in VALID_EVENT_TYPES:
            issues.append(f"event[{i}] 非标准事件类型: {etype}")

        # 日期合法性检查
        date_str = e.get("event_date", "")
        if date_str:
            try:
                # 支持多种日期格式: YYYY-MM-DD, YYYY-MM, YYYY
                if len(date_str) >= 7:
                    y = int(date_str[:4])
                    m = int(date_str[5:7])
                    if not (1990 <= y <= 2030 and 1 <= m <= 12):
                        issues.append(f"event[{i}] 日期异常: {date_str}")
            except (ValueError, IndexError):
                issues.append(f"event[{i}] 日期格式错误: {date_str}")

        # evidence 可回源性检查
        evidence = e.get("evidence_text", "")
        if evidence:
            for kw in SUMMARY_PATTERNS:
                if kw in evidence[:50]:
                    evidence_issues += 1
                    issues.append(f"event[{i}] evidence_text 含概括性语言('{kw}')，应为原文逐字摘录")
                    break
            # 至少应有50字符的原文
            if len(evidence) < 30:
                issues.append(f"event[{i}] evidence_text 过短({len(evidence)}字)，不足以验证")

        # notes 字段检查
        notes = e.get("notes", "")
        if not notes and evidence_issues == 0:
            # 如果有概括性内容，应该放在 notes 里
            pass  # notes 是可选字段，不强求

        # 投资人检查
        investors = e.get("investors", [])
        for j, inv in enumerate(investors):
            inv_missing = [f for f in REQUIRED_INVESTOR_FIELDS if f not in inv]
            if inv_missing:
                event_issues += 1
                issues.append(f"event[{i}]投资人[{j}]缺少字段: {inv_missing}")
            # is_pevc 必须是 yes/no/uncertain
            is_pevc = inv.get("is_pevc", "")
            if is_pevc and is_pevc not in ("yes", "no", "uncertain"):
                issues.append(f"event[{i}]投资人[{j}] is_pevc 值非法: {is_pevc}")

    details["event_field_issues"] = event_issues
    details["evidence_summary_issues"] = evidence_issues

    # 4. 事件类型合理性
    if len(events) > 0:
        types = [e.get("event_type") for e in events]
        details["has_setup_event"] = any(t in ["设立", "VIE搭建"] for t in types)
        details["has_change_event"] = any(t in ["整体变更"] for t in types)

    # 5. 日期区间检查
    dates = [e.get("event_date") for e in events if e.get("event_date")]
    if dates:
        dates.sort()
        details["date_range"] = f"{dates[0]} → {dates[-1]}"
        try:
            first_y = int(dates[0][:4])
            last_y = int(dates[-1][:4])
            if last_y - first_y > 40:
                issues.append(f"融资跨度异常: {dates[0]} → {dates[-1]} ({last_y-first_y}年)")
        except:
            pass

    # 判定
    critical_issues = [i for i in issues if "缺失" in i or "格式错误" in i or "异常" in i]
    if not issues:
        overall = "PASS"
    elif critical_issues:
        overall = "FAIL"
    else:
        overall = "WARN"

    return overall, issues, details


def main():
    print("=" * 60)
    print("  JSON Schema 校验 (新格式: financing_events 顶层)")
    print("=" * 60)

    all_results = []
    now = datetime.now()

    # 扫描所有公司目录
    company_dirs = sorted(d for d in OUTPUTS_DIR.glob("*") if d.is_dir() and not d.name.startswith("."))
    # 过滤 week* 目录
    company_dirs = [d for d in company_dirs if not d.name.startswith("week")]

    print(f"\n发现 {len(company_dirs)} 家公司目录\n")

    for d in company_dirs:
        json_files = list(d.glob("*结构化.json")) or list(d.glob("*融资历史.json"))
        if not json_files:
            all_results.append({
                "company": d.name, "overall": "FAIL",
                "issues": ["JSON文件缺失"], "details": {}
            })
            continue

        overall, issues, details = validate_company(json_files[0])
        all_results.append({
            "company": d.name,
            "overall": overall,
            "issues": issues,
            "details": details,
        })

        icon = {"PASS": "PASS", "WARN": "WARN", "FAIL": "FAIL"}
        print(f"  [{icon.get(overall, '?')}] {d.name:35s} | events={details.get('event_count','?'):2d} "
              f"evidence_ok={'Y' if not details.get('evidence_summary_issues') else 'N'} "
              f"| {len(issues)} issue(s)")
        for iss in issues[:3]:
            print(f"       - {iss}")

    # 统计
    pass_cnt = sum(1 for r in all_results if r["overall"] == "PASS")
    warn_cnt = sum(1 for r in all_results if r["overall"] == "WARN")
    fail_cnt = sum(1 for r in all_results if r["overall"] == "FAIL")

    print(f"\n{'='*60}")
    print(f"  结果: {pass_cnt} PASS / {warn_cnt} WARN / {fail_cnt} FAIL")
    print(f"{'='*60}")

    # 保存校验报告
    run_id = now.strftime("%Y%m%d_%H%M%S")
    report_path = LOG_DIR / f"validation_report_{run_id}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "validated_at": now.isoformat(),
            "schema_version": "2.0",
            "results": all_results,
            "summary": {"pass": pass_cnt, "warn": warn_cnt, "fail": fail_cnt}
        }, f, ensure_ascii=False, indent=2)
    print(f"\n报告: {report_path}")

    return 0 if fail_cnt == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
