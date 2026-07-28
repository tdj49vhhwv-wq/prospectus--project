#!/usr/bin/env python3
"""Analyze all stock structured JSON files, generate field schemas and anomaly reports."""

import json
import os
from datetime import datetime
from collections import defaultdict

BASE_DIR = "/Users/zhaobingqing/Documents/GitHub/prospectus-pevc-project"
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
SCHEMA_DIR = os.path.join(BASE_DIR, "schema")

# Define expected schema
COMPANY_FIELDS = {
    "company_name": {"type": "string", "required": True, "description": "公司全称"},
    "stock_code": {"type": "string", "required": True, "description": "股票代码"},
    "exchange": {"type": "string", "required": True, "description": "交易所", "enum": ["上交所", "深交所", "北交所"]},
    "board": {"type": "string", "required": True, "description": "上市板块", "enum": ["主板", "创业板", "科创板", "北交所"]},
    "listing_date": {"type": "string", "required": True, "description": "上市日期 (YYYY-MM-DD)"},
    "prospectus_title": {"type": "string", "required": True, "description": "招股书标题"},
    "prospectus_url": {"type": "string", "required": True, "description": "招股书URL"},
    "prospectus_version": {"type": "string", "required": True, "description": "招股书版本", "enum": ["正式稿", "申报稿", "上会稿"]},
    "prospectus_date": {"type": "string", "required": True, "description": "招股书日期 (YYYY-MM-DD)"},
    "financing_events": {"type": "array", "required": True, "description": "融资事件列表"},
    "processing": {"type": "object", "required": False, "description": "处理状态"},
}

EVENT_FIELDS = {
    "event_order": {"type": "integer", "required": True, "description": "事件顺序号"},
    "event_date": {"type": "string", "required": True, "description": "事件日期"},
    "date_type": {"type": "string", "required": True, "description": "日期类型", "enum": ["工商变更日", "签约日", "股东大会日", "未说明"]},
    "event_type": {"type": "string", "required": True, "description": "事件类型", "enum": ["增资", "股权转让", "增资及股权转让", "其他"]},
    "disclosed_round": {"type": "string", "required": True, "description": "披露轮次"},
    "inferred_round": {"type": "string", "required": True, "description": "推断轮次"},
    "round_inference_basis": {"type": "string", "required": True, "description": "轮次推断依据"},
    "total_investment_amount": {"type": "number|null", "required": False, "description": "总投资金额(万元)"},
    "currency": {"type": "string", "required": True, "description": "币种", "enum": ["CNY", "USD", "HKD"]},
    "share_price": {"type": "number|null", "required": False, "description": "每股价格(元)"},
    "pre_money_valuation": {"type": "number|null", "required": False, "description": "投前估值(万元)"},
    "post_money_valuation": {"type": "number|null", "required": False, "description": "投后估值(万元)"},
    "valuation_basis": {"type": "string|null", "required": False, "description": "估值依据"},
    "investors": {"type": "array", "required": True, "description": "投资者列表"},
    "source_section": {"type": "string", "required": True, "description": "来源章节"},
    "source_page": {"type": "string", "required": True, "description": "来源页码"},
    "evidence_text": {"type": "string", "required": True, "description": "证据文本"},
    "confidence": {"type": "string", "required": True, "description": "置信度", "enum": ["high", "medium", "low"]},
}

INVESTOR_FIELDS = {
    "investor_original_name": {"type": "string", "required": True, "description": "投资者原始名称"},
    "investor_short_name": {"type": "string", "required": True, "description": "投资者简称"},
    "investor_type": {"type": "string", "required": True, "description": "投资者类型", "enum": ["PE", "VC", "产业资本", "政府基金", "自然人", "员工持股平台", "其他"]},
    "is_pevc": {"type": "string", "required": True, "description": "是否PE/VC", "enum": ["yes", "no", "uncertain"]},
    "investment_amount": {"type": "number|null", "required": False, "description": "投资金额(万元)"},
    "shares_acquired": {"type": "number|null", "required": False, "description": "获得股份数"},
    "shareholding_ratio_after_event": {"type": "string|null", "required": False, "description": "事件后持股比例"},
    "exit_status_before_ipo": {"type": "string", "required": True, "description": "IPO前退出状态", "enum": ["未退出", "全部退出", "部分退出"]},
}

PROCESSING_FIELDS = {
    "download_status": {"type": "string", "required": False, "enum": ["success", "failed", "pending"]},
    "parse_status": {"type": "string", "required": False, "enum": ["success", "failed", "pending"]},
    "locate_status": {"type": "string", "required": False, "enum": ["success", "failed", "pending"]},
    "extract_status": {"type": "string", "required": False, "enum": ["success", "failed", "pending"]},
    "review_status": {"type": "string", "required": False, "enum": ["checked", "unchecked"]},
}


def check_field(value, field_def, field_name, path):
    """Check a single field and return anomalies."""
    anomalies = []
    expected_type = field_def["type"]
    is_required = field_def.get("required", False)

    if value is None:
        if is_required:
            anomalies.append({
                "path": path,
                "field": field_name,
                "type": "缺失必填字段",
                "detail": f"必填字段 '{field_name}' 为 null",
                "severity": "high"
            })
        return anomalies

    # Type check
    if "|" in expected_type:
        valid_types = expected_type.split("|")
        type_ok = False
        for vt in valid_types:
            if vt == "null" and value is None:
                type_ok = True
                break
            if vt == "number" and isinstance(value, (int, float)):
                type_ok = True
                break
            if vt == "string" and isinstance(value, str):
                type_ok = True
                break
            if vt == "integer" and isinstance(value, int) and not isinstance(value, bool):
                type_ok = True
                break
        if not type_ok:
            anomalies.append({
                "path": path,
                "field": field_name,
                "type": "类型错误",
                "detail": f"期望类型 {expected_type}, 实际类型 {type(value).__name__}, 值: {value}",
                "severity": "high"
            })
    else:
        type_map = {"string": str, "number": (int, float), "integer": int, "array": list, "object": dict}
        expected = type_map.get(expected_type)
        if expected:
            if isinstance(expected, tuple):
                if not isinstance(value, expected):
                    anomalies.append({
                        "path": path,
                        "field": field_name,
                        "type": "类型错误",
                        "detail": f"期望类型 {expected_type}, 实际类型 {type(value).__name__}",
                        "severity": "high"
                    })
            elif not isinstance(value, expected):
                anomalies.append({
                    "path": path,
                    "field": field_name,
                    "type": "类型错误",
                    "detail": f"期望类型 {expected_type}, 实际类型 {type(value).__name__}",
                    "severity": "high"
                })

    # Enum check
    if "enum" in field_def and value is not None:
        if value not in field_def["enum"]:
            anomalies.append({
                "path": path,
                "field": field_name,
                "type": "枚举值异常",
                "detail": f"'{value}' 不在允许的值 {field_def['enum']} 中",
                "severity": "medium"
            })

    # Empty string check
    if isinstance(value, str) and value.strip() == "" and is_required:
        anomalies.append({
            "path": path,
            "field": field_name,
            "type": "空字符串",
            "detail": f"必填字段 '{field_name}' 为空字符串",
            "severity": "high"
        })

    return anomalies


def analyze_structured_data(data, stock_name):
    """Analyze structured JSON data for a stock."""
    anomalies = []
    field_presence = defaultdict(lambda: {"present": 0, "null": 0, "total": 0})

    company = data.get("company", data)
    if not isinstance(company, dict):
        anomalies.append({
            "path": "$",
            "field": "company",
            "type": "结构错误",
            "detail": "缺少 company 对象",
            "severity": "critical"
        })
        return anomalies, field_presence

    # Check company-level fields
    for field_name, field_def in COMPANY_FIELDS.items():
        if field_name in ["financing_events", "processing"]:
            continue
        field_presence[field_name]["total"] += 1
        value = company.get(field_name)
        if value is not None:
            field_presence[field_name]["present"] += 1
        else:
            field_presence[field_name]["null"] += 1
        anomalies.extend(check_field(value, field_def, field_name, f"$.company.{field_name}"))

    # Check date format
    for date_field in ["listing_date", "prospectus_date"]:
        value = company.get(date_field)
        if value and isinstance(value, str):
            if len(value) != 10 or value[4] != '-' or value[7] != '-':
                anomalies.append({
                    "path": f"$.company.{date_field}",
                    "field": date_field,
                    "type": "日期格式错误",
                    "detail": f"'{value}' 不符合 YYYY-MM-DD 格式",
                    "severity": "high"
                })

    # Check financing events
    events = company.get("financing_events", [])
    if not isinstance(events, list):
        anomalies.append({
            "path": "$.company.financing_events",
            "field": "financing_events",
            "type": "类型错误",
            "detail": "financing_events 应为数组",
            "severity": "critical"
        })
        return anomalies, field_presence

    field_presence["financing_events_count"] = {"present": len(events), "null": 0, "total": len(events)}

    if len(events) == 0:
        anomalies.append({
            "path": "$.company.financing_events",
            "field": "financing_events",
            "type": "数据缺失",
            "detail": "融资事件列表为空",
            "severity": "critical"
        })

    for i, event in enumerate(events):
        event_path = f"$.company.financing_events[{i}]"

        for field_name, field_def in EVENT_FIELDS.items():
            if field_name == "investors":
                continue
            field_presence[field_name]["total"] += 1
            value = event.get(field_name)
            if value is not None:
                field_presence[field_name]["present"] += 1
            else:
                field_presence[field_name]["null"] += 1
            anomalies.extend(check_field(value, field_def, field_name, f"{event_path}.{field_name}"))

        # Check event_date format
        event_date = event.get("event_date")
        if event_date and isinstance(event_date, str):
            # Allow year-only or year-month dates
            if "-" in event_date:
                parts = event_date.split("-")
                if len(parts) == 1:
                    pass  # year only
                elif len(parts) == 2:
                    pass  # year-month
                elif len(parts) == 3:
                    if len(event_date) != 10:
                        anomalies.append({
                            "path": f"{event_path}.event_date",
                            "field": "event_date",
                            "type": "日期格式异常",
                            "detail": f"'{event_date}' 日期格式不标准",
                            "severity": "low"
                        })

        # Specific: check inferred_round for duplicate characters ("轮轮" bug)
        inferred_round = event.get("inferred_round", "")
        if isinstance(inferred_round, str) and "轮轮" in inferred_round:
            anomalies.append({
                "path": f"{event_path}.inferred_round",
                "field": "inferred_round",
                "type": "数据录入错误",
                "detail": f"推断轮次存在重复字符: '{inferred_round}' (应去掉末尾多余的'轮'字)",
                "severity": "high"
            })

        # Specific: check if date covers too wide a range
        if event_date and isinstance(event_date, str) and "-" in event_date:
            parts = event_date.split("-")
            if len(parts) == 2 and parts[1].isdigit():
                # e.g. "2009" (year only, no dash) is fine
                pass
            # Check for range spanning multiple years like "2015-2020"
            if event_date.count("-") == 1 and len(parts) == 2 and len(parts[0]) == 4 and len(parts[1]) == 4:
                anomalies.append({
                    "path": f"{event_path}.event_date",
                    "field": "event_date",
                    "type": "日期跨度过大",
                    "detail": f"事件日期 '{event_date}' 跨越多年度，应拆分为独立事件",
                    "severity": "high"
                })

        # Check investors
        investors = event.get("investors", [])
        if not isinstance(investors, list) or len(investors) == 0:
            anomalies.append({
                "path": f"{event_path}.investors",
                "field": "investors",
                "type": "数据缺失",
                "detail": "投资者列表为空",
                "severity": "high"
            })

        total_investor_amount = 0
        for j, investor in enumerate(investors):
            inv_path = f"{event_path}.investors[{j}]"
            for field_name, field_def in INVESTOR_FIELDS.items():
                field_presence[field_name]["total"] += 1
                value = investor.get(field_name)
                if value is not None:
                    field_presence[field_name]["present"] += 1
                else:
                    field_presence[field_name]["null"] += 1
                anomalies.extend(check_field(value, field_def, field_name, f"{inv_path}.{field_name}"))

            # Sum investor amounts
            amt = investor.get("investment_amount")
            if isinstance(amt, (int, float)):
                total_investor_amount += amt

        # Check if sum of investor amounts matches total_investment_amount
        total_amt = event.get("total_investment_amount")
        if isinstance(total_amt, (int, float)) and total_amt > 0 and total_investor_amount > 0:
            diff = abs(total_amt - total_investor_amount)
            if diff > 1:  # Allow rounding difference of 1
                anomalies.append({
                    "path": event_path,
                    "field": "total_investment_amount",
                    "type": "金额不一致",
                    "detail": f"总投资金额 {total_amt} 与投资者出资金额之和 {total_investor_amount} 不匹配 (差异: {diff:.2f})",
                    "severity": "high"
                })

        # Specific: event_type is "增资" but total_investment_amount is null or 0
        event_type = event.get("event_type")
        if event_type == "增资":
            amt = event.get("total_investment_amount")
            if amt is None:
                anomalies.append({
                    "path": event_path,
                    "field": "total_investment_amount",
                    "type": "数据缺失",
                    "detail": f"事件类型为'增资'但总投资金额为 null",
                    "severity": "medium"
                })

        # Check confidence level
        confidence = event.get("confidence")
        if confidence == "low":
            anomalies.append({
                "path": event_path,
                "field": "confidence",
                "type": "低置信度",
                "detail": f"事件#{event.get('event_order')} 置信度为 low，数据可能不准确",
                "severity": "medium"
            })

    # Check processing status
    processing = company.get("processing", {})
    if isinstance(processing, dict):
        for field_name, field_def in PROCESSING_FIELDS.items():
            value = processing.get(field_name)
            anomalies.extend(check_field(value, field_def, field_name, f"$.company.processing.{field_name}"))

        # Check if all statuses are success
        status_fields = ["download_status", "parse_status", "locate_status", "extract_status"]
        for sf in status_fields:
            if processing.get(sf) != "success":
                anomalies.append({
                    "path": f"$.company.processing.{sf}",
                    "field": sf,
                    "type": "处理未成功",
                    "detail": f"{sf} = '{processing.get(sf)}'",
                    "severity": "medium"
                })

        if processing.get("review_status") != "checked":
            anomalies.append({
                "path": "$.company.processing.review_status",
                "field": "review_status",
                "type": "未审核",
                "detail": "数据尚未经过人工审核",
                "severity": "low"
            })

    return anomalies, field_presence


def analyze_basic_data(data, stock_name):
    """Analyze basic (non-structured) JSON data."""
    anomalies = []

    if not isinstance(data, dict):
        return [{"path": "$", "field": "root", "type": "结构错误", "detail": "根对象不是字典", "severity": "critical"}]

    # Check if it's the old format (no company wrapper)
    if "company" not in data:
        anomalies.append({
            "path": "$",
            "field": "structure",
            "type": "缺少结构化数据",
            "detail": "数据未使用 company 包装格式，缺少结构化融资历史",
            "severity": "critical"
        })

    events = data.get("financing_events", [])
    if len(events) == 0:
        anomalies.append({
            "path": "$.financing_events",
            "field": "financing_events",
            "type": "无融资事件",
            "detail": "融资事件列表为空，可能招股书解析不完整",
            "severity": "critical"
        })

    # Check individual event quality
    for i, event in enumerate(events):
        path = f"$.financing_events[{i}]"
        if not isinstance(event, dict):
            continue
        if event.get("date") is None:
            anomalies.append({
                "path": f"{path}.date",
                "field": "date",
                "type": "日期缺失",
                "detail": f"事件#{i+1} 缺少日期",
                "severity": "high"
            })
        if not event.get("participants"):
            anomalies.append({
                "path": f"{path}.participants",
                "field": "participants",
                "type": "参与者缺失",
                "detail": f"事件#{i+1} 缺少参与者信息",
                "severity": "medium"
            })

    return anomalies


def generate_schema_doc(stock_name, data):
    """Generate a schema definition document for a stock."""
    lines = []
    lines.append(f"# {stock_name} — 字段Schema定义\n")
    lines.append(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    company = data.get("company", data)
    company_name = company.get("company_name", stock_name) if isinstance(company, dict) else stock_name
    lines.append(f"**公司名称**: {company_name}  \n")
    if isinstance(company, dict):
        lines.append(f"**股票代码**: {company.get('stock_code', 'N/A')}  \n")
        lines.append(f"**交易所**: {company.get('exchange', 'N/A')}  \n")
        lines.append(f"**上市板块**: {company.get('board', 'N/A')}  \n")
        lines.append(f"**上市日期**: {company.get('listing_date', 'N/A')}  \n")
    lines.append("")

    # Check if structured
    has_structured = isinstance(company, dict) and "financing_events" in company
    data_format = "结构化格式 (含完整字段定义)" if has_structured else "基础格式 (字段不完整)"

    lines.append(f"**数据格式**: {data_format}\n")
    lines.append("---\n")

    lines.append("## 一、公司基本信息字段\n")
    lines.append("| 字段名 | 类型 | 必填 | 说明 | 实际值 |")
    lines.append("|--------|------|------|------|--------|")
    for field_name, field_def in COMPANY_FIELDS.items():
        if field_name in ["financing_events", "processing"]:
            continue
        value = company.get(field_name) if isinstance(company, dict) else data.get(field_name)
        status = "✓" if value is not None else "✗ 缺失"
        lines.append(f"| {field_name} | {field_def['type']} | {'是' if field_def['required'] else '否'} | {field_def['description']} | {status} |")
    lines.append("")

    lines.append("## 二、融资事件字段\n")
    lines.append("| 字段名 | 类型 | 必填 | 说明 |")
    lines.append("|--------|------|------|------|")
    for field_name, field_def in EVENT_FIELDS.items():
        if field_name == "investors":
            continue
        lines.append(f"| {field_name} | {field_def['type']} | {'是' if field_def['required'] else '否'} | {field_def['description']} |")
    lines.append("")

    lines.append("## 三、投资者字段\n")
    lines.append("| 字段名 | 类型 | 必填 | 说明 |")
    lines.append("|--------|------|------|------|")
    for field_name, field_def in INVESTOR_FIELDS.items():
        lines.append(f"| {field_name} | {field_def['type']} | {'是' if field_def['required'] else '否'} | {field_def['description']} |")
    lines.append("")

    lines.append("## 四、处理状态字段\n")
    lines.append("| 字段名 | 类型 | 必填 | 说明 |")
    lines.append("|--------|------|------|------|")
    for field_name, field_def in PROCESSING_FIELDS.items():
        lines.append(f"| {field_name} | {field_def['type']} | {'是' if field_def['required'] else '否'} | {field_def.get('description', '')} |")
    lines.append("")

    if has_structured:
        events = company.get("financing_events", [])
        lines.append("## 五、融资事件概览\n")
        lines.append(f"**事件总数**: {len(events)}\n")
        for event in events:
            lines.append(f"- **事件#{event.get('event_order')}** | {event.get('event_date')} | {event.get('event_type')} | "
                        f"推断轮次: {event.get('inferred_round')} | 金额: {event.get('total_investment_amount')} | "
                        f"置信度: {event.get('confidence')}")

    return "\n".join(lines)


def generate_anomaly_doc(stock_name, data, anomalies, field_presence):
    """Generate an anomaly report document for a stock."""
    lines = []
    lines.append(f"# {stock_name} — 字段检验与异常记录\n")
    lines.append(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    company = data.get("company", data)
    company_name = company.get("company_name", stock_name) if isinstance(company, dict) else stock_name
    lines.append(f"**公司名称**: {company_name}\n")

    # Count by severity
    severity_count = defaultdict(int)
    for a in anomalies:
        severity_count[a["severity"]] += 1

    lines.append(f"**异常总数**: {len(anomalies)}")
    lines.append(f" (critical: {severity_count['critical']}, high: {severity_count['high']}, "
                f"medium: {severity_count['medium']}, low: {severity_count['low']})\n")

    lines.append("---\n")

    if not anomalies:
        lines.append("## 检验结果：未发现异常\n")
        lines.append("所有字段均通过检验。\n")
    else:
        # Group by severity
        for severity, label in [("critical", "严重"), ("high", "高"), ("medium", "中"), ("low", "低")]:
            group = [a for a in anomalies if a["severity"] == severity]
            if not group:
                continue
            lines.append(f"## {label}优先级异常 ({len(group)}项)\n")
            lines.append("| 路径 | 字段 | 异常类型 | 详情 |")
            lines.append("|------|------|----------|------|")
            for a in group:
                lines.append(f"| {a['path']} | {a['field']} | {a['type']} | {a['detail']} |")
            lines.append("")

    # Field completeness summary
    lines.append("---\n")
    lines.append("## 字段完整性统计\n")
    lines.append("| 字段名 | 出现次数 | 非空次数 | 空值次数 | 完整率 |")
    lines.append("|--------|----------|----------|----------|--------|")
    for field_name, stats in sorted(field_presence.items()):
        total = stats["total"]
        present = stats["present"]
        null_count = stats["null"]
        rate = f"{present/total*100:.1f}%" if total > 0 else "N/A"
        lines.append(f"| {field_name} | {total} | {present} | {null_count} | {rate} |")

    return "\n".join(lines)


def get_data_format(data):
    """Determine data format type."""
    if not isinstance(data, dict):
        return "invalid"
    if "company" in data and isinstance(data["company"], dict):
        company = data["company"]
        if "financing_events" in company and isinstance(company["financing_events"], list):
            if len(company["financing_events"]) > 0 and "event_order" in company["financing_events"][0]:
                return "structured_nested"  # 5家公司_合并格式
    if "financing_events" in data and isinstance(data["financing_events"], list):
        if len(data["financing_events"]) > 0 and "event_order" in data["financing_events"][0]:
            return "structured_flat"  # 直接company格式
    return "basic"  # 基础格式


def main():
    os.makedirs(SCHEMA_DIR, exist_ok=True)

    # Map stock names to their data files
    stocks = {}

    # Structured JSON files in individual stock directories
    for stock_dir in ["黄山谷捷", "赛分科技", "三联锻造", "影石创新", "云汉芯城"]:
        dir_path = os.path.join(OUTPUTS_DIR, stock_dir)
        w1_path = os.path.join(OUTPUTS_DIR, "week1_sample_json")
        structured_file = None

        for search_dir in [dir_path, w1_path]:
            f = os.path.join(search_dir, f"{stock_dir}_融资历史_结构化.json")
            if os.path.exists(f):
                structured_file = f
                break

        if structured_file:
            with open(structured_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            stocks[stock_dir] = {"data": data, "format": get_data_format(data), "file": structured_file}
        else:
            # Check for basic JSON
            basic_file = os.path.join(dir_path, f"{stock_dir}_融资历史.json")
            if os.path.exists(basic_file):
                with open(basic_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                stocks[stock_dir] = {"data": data, "format": "basic", "file": basic_file}

    # Basic JSON files for stocks without structured data
    for stock_dir in ["三协电机", "星空测控", "友声股份"]:
        if stock_dir not in stocks:
            basic_file = os.path.join(OUTPUTS_DIR, stock_dir, f"{stock_dir}_融资历史.json")
            if os.path.exists(basic_file):
                with open(basic_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                stocks[stock_dir] = {"data": data, "format": "basic", "file": basic_file}

    # Use standalone structured files as primary source (preserves original data including duplicate key bugs)
    # Only use merged file as fallback for stocks not found in standalone files

    print(f"共发现 {len(stocks)} 个股票的数据文件\n")

    for stock_name, stock_info in sorted(stocks.items()):
        data = stock_info["data"]
        fmt = stock_info["format"]

        print(f"--- 处理: {stock_name} (格式: {fmt}) ---")

        if fmt in ("structured_flat", "structured_nested"):
            anomalies, field_presence = analyze_structured_data(data, stock_name)
        else:
            anomalies = analyze_basic_data(data, stock_name)
            field_presence = defaultdict(lambda: {"present": 0, "null": 0, "total": 0})

        # Generate schema doc
        schema_content = generate_schema_doc(stock_name, data)
        schema_path = os.path.join(SCHEMA_DIR, f"{stock_name}_schema.md")
        with open(schema_path, "w", encoding="utf-8") as f:
            f.write(schema_content)
        print(f"  -> 写入 {schema_path}")

        # Generate anomaly doc
        anomaly_content = generate_anomaly_doc(stock_name, data, anomalies, field_presence)
        anomaly_path = os.path.join(SCHEMA_DIR, f"{stock_name}_异常记录.md")
        with open(anomaly_path, "w", encoding="utf-8") as f:
            f.write(anomaly_content)
        print(f"  -> 写入 {anomaly_path}")

        print(f"  异常数: {len(anomalies)}")
        for a in anomalies:
            print(f"    [{a['severity']}] {a['path']}: {a['detail']}")
        print()

    # Generate a summary index
    generate_summary(stocks)
    print("完成！所有文件已生成到 schema/ 目录。")


def generate_summary(stocks):
    """Generate a summary index of all schemas."""
    lines = []
    lines.append("# Schema & 异常记录 索引\n")
    lines.append(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append("## 文件列表\n")
    lines.append("| 股票名称 | 股票代码 | 数据格式 | Schema文件 | 异常记录 |")
    lines.append("|----------|----------|----------|------------|----------|")

    for stock_name in sorted(stocks.keys()):
        info = stocks[stock_name]
        data = info["data"]
        company = data.get("company", data)
        stock_code = company.get("stock_code", "N/A") if isinstance(company, dict) else data.get("stock_code", "N/A")
        fmt = info["format"]
        fmt_label = {"structured_nested": "结构化(嵌套)", "structured_flat": "结构化(扁平)", "basic": "基础格式"}.get(fmt, fmt)
        schema_file = f"[{stock_name}_schema.md]({stock_name}_schema.md)"
        anomaly_file = f"[{stock_name}_异常记录.md]({stock_name}_异常记录.md)"
        lines.append(f"| {stock_name} | {stock_code} | {fmt_label} | {schema_file} | {anomaly_file} |")

    lines.append("")
    lines.append("## 数据质量总览\n")
    lines.append("| 股票名称 | 格式 | 融资事件数 | 主要问题 |")
    lines.append("|----------|------|------------|----------|")

    quality_notes = {
        "黄山谷捷": "结构化, 6事件, 数据完整, 质量高",
        "赛分科技": "结构化, 3事件, 置信度低, 大量null, 缺少估值数据",
        "三联锻造": "结构化, 5事件, 4/5事件date_type为'未说明'",
        "三协电机": "基础格式, 1事件, 无结构化数据, 缺少日期和金额",
        "星空测控": "基础格式, 0事件, 无结构化数据, 招股书解析不完整",
        "影石创新": "结构化, 4事件, 事件2跨5年度需拆分, 缺少早期轮次细节",
        "友声股份": "基础格式, 1事件, 无结构化数据, 参与者信息异常",
        "云汉芯城": "结构化, 8事件, inferred_round存在'轮轮'重复字符bug, is_pevc存在'uncertain'值",
    }

    for stock_name in sorted(stocks.keys()):
        data = stocks[stock_name]["data"]
        company = data.get("company", data)
        fmt = stocks[stock_name]["format"]
        fmt_label = "结构化" if "structured" in fmt else "基础"
        events_count = len(company.get("financing_events", [])) if isinstance(company, dict) else len(data.get("financing_events", []))
        notes = quality_notes.get(stock_name, "")
        lines.append(f"| {stock_name} | {fmt_label} | {events_count} | {notes} |")

    summary_path = os.path.join(SCHEMA_DIR, "README.md")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
