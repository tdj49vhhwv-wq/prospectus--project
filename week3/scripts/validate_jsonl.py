#!/usr/bin/env python3
"""
JSONL 校验: Pydantic Schema + 详细 Cross-Check

校验维度:
  1. JSONL 逐行解析 + record_type 检查
  2. 必填字段非空检查 (PDF页码/日期/认购方/股东名称/原文证据)
  3. 数字列可解析为数值
  4. 每家公司 t0 股权结构存在性
  5. 同一时点股东持股数合计 ≈ 总股本
  6. 相邻时点: 老股东持股变化 (保持/稀释/退出)
  7. 认缴流量 → 存量对应: 新增认购方在增资后快照中的持股数

输出:
  - logs/schema_validation_log.csv
  - logs/cross_check_summary.csv (含完整数字列)
"""
import sys
import json
import csv
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from schemas.models import SubscriptionFlow, EquitySnapshot
from pydantic import ValidationError

JSONL_DIR = PROJECT_ROOT / "outputs" / "week2_jsonl"
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

_schema_rows = []
_cross_rows = []


def log_schema(company, record_type, check_type, status, detail=""):
    _schema_rows.append(dict(company=company, record_type=record_type,
                             check_type=check_type, status=status, detail=detail))


def log_cross(company, snap_from, snap_to, shareholder,
              prev_shares, prev_capital, change_shares,
              expected_shares, pdf_shares, diff, status="", detail=""):
    _cross_rows.append(dict(
        company=company,
        snapshot_date_from=snap_from or "",
        snapshot_date_to=snap_to or "",
        shareholder_name=shareholder,
        previous_shares=fmt_num(prev_shares),
        previous_capital=fmt_num(prev_capital),
        subscription_change=fmt_num(change_shares),
        expected_shares=fmt_num(expected_shares),
        pdf_disclosed_shares=fmt_num(pdf_shares),
        difference=fmt_num(diff),
        status=status,
        detail=detail,
    ))


def fmt_num(v):
    if v is None:
        return ""
    return round(v, 4)


def parse_date(s):
    """提取 YYYY-MM 用于排序"""
    m = re.match(r'(\d{4})-(\d{2})', str(s))
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return s


def validate_file(path):
    company = path.stem
    with open(path, encoding="utf-8") as f:
        lines = [json.loads(ln) for ln in f if ln.strip()]

    sub_flows = []
    eq_snaps = []
    issues = []

    # ── 逐行解析 + Schema 检查 ──
    for i, raw in enumerate(lines, 1):
        rt = raw.get("record_type", "")
        if rt not in ("subscription_flow", "equity_snapshot"):
            issues.append(f"line {i}: 非法 record_type={rt}")
            log_schema(company, rt or "unknown", "record_type", "FAIL", f"line={i}")
            continue

        # 必填字段检查
        if rt == "subscription_flow":
            for fld in ["source_page", "subscription_date", "subscriber_name", "evidence_text"]:
                if not raw.get(fld):
                    issues.append(f"line {i}: {fld} 为空")
                    log_schema(company, rt, f"required_{fld}", "FAIL", f"line={i}")
            # 数字列
            for fld in ["shares_subscribed", "amount_subscribed", "price_per_share"]:
                v = raw.get(fld)
                if v is not None:
                    try:
                        float(v)
                    except (ValueError, TypeError):
                        issues.append(f"line {i}: {fld}={v} 非数值")
                        log_schema(company, rt, f"numeric_{fld}", "FAIL", f"line={i}")

        if rt == "equity_snapshot":
            for fld in ["source_page", "snapshot_date", "snapshot_type", "shareholder_name", "evidence_text"]:
                if not raw.get(fld):
                    issues.append(f"line {i}: {fld} 为空")
                    log_schema(company, rt, f"required_{fld}", "FAIL", f"line={i}")
            for fld in ["total_shares", "total_capital", "shares_held", "capital_contribution"]:
                v = raw.get(fld)
                if v is not None:
                    try:
                        float(v)
                    except (ValueError, TypeError):
                        issues.append(f"line {i}: {fld}={v} 非数值")
                        log_schema(company, rt, f"numeric_{fld}", "FAIL", f"line={i}")

        # Pydantic
        try:
            if rt == "subscription_flow":
                sub_flows.append(SubscriptionFlow.model_validate(raw))
                log_schema(company, rt, "schema", "PASS", f"line={i}")
            else:
                eq_snaps.append(EquitySnapshot.model_validate(raw))
                log_schema(company, rt, "schema", "PASS", f"line={i}")
        except ValidationError as e:
            for err in e.errors():
                issues.append(f"line {i}: {err['loc']} — {err['msg']}")
            log_schema(company, rt, "schema", "FAIL", f"line={i}, errors={e.error_count()}")

    # ── t0 检查 ──
    if not eq_snaps:
        log_schema(company, "equity_snapshot", "t0_check", "WARN", "无股权存量记录")
    else:
        log_schema(company, "equity_snapshot", "t0_check", "PASS",
                   f"最早快照: {eq_snaps[0].snapshot_date}")

    # ── 价格×数量≈金额 (subscription_flow) ──
    for i, sf in enumerate(sub_flows):
        if sf.price_per_share and sf.shares_subscribed and sf.amount_subscribed:
            expected = sf.price_per_share * sf.shares_subscribed
            actual = sf.amount_subscribed
            if actual > 0:
                diff_pct = abs(expected - actual) / actual
                diff_abs = abs(expected - actual)
                # 差额>1万元 或 比例>1% → 待复核
                st = "待复核" if (diff_abs > 1.0 or diff_pct > 0.01) else "PASS"
                if st == "待复核":
                    issues.append(f"sub_flow[{i}] {sf.subscriber_name}: 价格×数量({expected:.0f})≠金额({actual:.0f})")
                log_cross(company, "", sf.subscription_date, sf.subscriber_name,
                          None, None, sf.shares_subscribed, expected, actual,
                          expected - actual, st, f"price×shares vs amount diff={diff_pct*100:.1f}%")

    # ── 股权快照按日期分组 ──
    snap_groups = defaultdict(list)
    for es in eq_snaps:
        key = f"{es.snapshot_date}|{es.snapshot_type}"
        snap_groups[key].append(es)

    sorted_keys = sorted(snap_groups.keys(), key=parse_date)
    snap_list = [(k, snap_groups[k]) for k in sorted_keys]

    # ── 同快照: 总股本/总出资额 一致性检查 ──
    for key, group in snap_groups.items():
        # 总股本一致性
        total_shares_vals = set(es.total_shares for es in group if es.total_shares is not None)
        if len(total_shares_vals) > 1:
            issues.append(f"snap [{key}]: 总股本不一致 {total_shares_vals}")
        # 总出资额一致性
        total_cap_vals = set(es.total_capital for es in group if es.total_capital is not None)
        if len(total_cap_vals) > 1:
            issues.append(f"snap [{key}]: 总出资额不一致 {total_cap_vals}")

        # 持股数合计 ≈ 总股本
        shares_sum = sum(es.shares_held for es in group if es.shares_held is not None)
        ts = next((es.total_shares for es in group if es.total_shares is not None), None)
        if shares_sum > 0 and ts is not None and ts > 0:
            diff = shares_sum - ts
            st = "待复核" if abs(diff) > 0.01 else "PASS"
            detail = f"持股合计{shares_sum:.1f}万股 vs 总股本{ts:.1f}万股"
            if st == "待复核":
                detail += " ←待复核"
            log_cross(company, "", key.split("|")[0], f"[合计 {len(group)}股东]",
                      None, None, None, shares_sum, ts, diff, st, detail)

    # ── 相邻时点追踪: 老股东变化 ──
    for idx in range(len(snap_list) - 1):
        key_prev, group_prev = snap_list[idx]
        key_curr, group_curr = snap_list[idx + 1]

        date_prev = key_prev.split("|")[0]
        date_curr = key_curr.split("|")[0]

        # 构建股东名→持股映射
        prev_map = {}
        for es in group_prev:
            prev_map[es.shareholder_name] = es

        curr_map = {}
        for es in group_curr:
            curr_map[es.shareholder_name] = es

        all_names = set(prev_map.keys()) | set(curr_map.keys())

        for name in all_names:
            prev_es = prev_map.get(name)
            curr_es = curr_map.get(name)

            prev_shares = prev_es.shares_held if prev_es else None

            # 找本次认购
            sub_change = None
            for sf in sub_flows:
                if sf.subscriber_name == name and sf.shares_subscribed:
                    sub_change = sf.shares_subscribed
                    break

            expected = (prev_shares + sub_change) if (prev_shares is not None and sub_change is not None) else None
            curr_shares = curr_es.shares_held if curr_es else None
            diff = (curr_shares - expected) if (curr_shares is not None and expected is not None) else None

            change_status = ""
            if curr_es is None and prev_es is not None:
                change_status = "退出"
            elif prev_es is None and curr_es is not None:
                change_status = "新增"
            elif prev_es and curr_es:
                if curr_shares and prev_shares:
                    if curr_shares < prev_shares:
                        change_status = "稀释"
                    elif curr_shares == prev_shares:
                        change_status = "保持"
                    else:
                        change_status = "增持"

            # 有差额时标记待复核
            review_mark = "待复核" if (diff is not None and abs(diff) > 0.001) else "PASS"
            detail_text = change_status
            if review_mark == "待复核":
                detail_text += " ←待复核"

            log_cross(company, date_prev, date_curr, name,
                      prev_shares,
                      prev_es.capital_contribution if prev_es else None,
                      sub_change,
                      expected,
                      curr_shares,
                      diff,
                      review_mark,
                      detail_text)


    # ── 认购合计对应相邻存量时点股本变化 ──
    # 按 subscription_date 分组 (YYYY-MM)，合计每个月的认购数量
    sub_by_month = defaultdict(float)
    for sf in sub_flows:
        if sf.subscription_date and sf.shares_subscribed:
            month_key = sf.subscription_date[:7]
            sub_by_month[month_key] += sf.shares_subscribed

    # 找相邻快照的总股本变化，与认购合计对比
    for idx in range(len(snap_list) - 1):
        key_prev, group_prev = snap_list[idx]
        key_curr, group_curr = snap_list[idx + 1]
        date_curr = key_curr.split("|")[0]

        ts_prev = next((es.total_shares for es in group_prev if es.total_shares is not None), None)
        ts_curr = next((es.total_shares for es in group_curr if es.total_shares is not None), None)

        tc_prev = next((es.total_capital for es in group_prev if es.total_capital is not None), None)
        tc_curr = next((es.total_capital for es in group_curr if es.total_capital is not None), None)

        # 找最接近的认购月合计
        sub_total = None
        for month_key, total in sorted(sub_by_month.items()):
            if month_key <= date_curr[:7]:
                sub_total = total

        if ts_prev is not None and ts_curr is not None and ts_curr != ts_prev:
            delta = ts_curr - ts_prev
            if sub_total is not None and sub_total > 0:
                diff = sub_total - delta
                st = "待复核" if abs(diff) > 0.01 else "PASS"
                dt = f"认购合计{sub_total:.1f}万股 vs 股本变化{delta:.1f}万股"
                if st == "待复核":
                    dt += " ←待复核"
                log_cross(company, date_curr, "", "[股本变化合计]",
                          ts_prev, None, sub_total, ts_prev + sub_total, ts_curr,
                          diff, st, dt)

        if tc_prev is not None and tc_curr is not None and tc_curr != tc_prev:
            delta_cap = tc_curr - tc_prev
            if sub_total is not None and sub_total > 0:
                diff_cap = sub_total - delta_cap
                st = "待复核" if abs(diff_cap) > 0.01 else "PASS"
                dt = f"认购合计{sub_total:.1f}万股 vs 出资额变化{delta_cap:.1f}万元"
                log_cross(company, date_curr, "", "[出资额变化合计]",
                          tc_prev, None, sub_total, tc_prev + sub_total, tc_curr,
                          diff_cap, st, dt)

    # ── 认缴→存量对应 ──
    for sf in sub_flows:
        found = False
        for key, group in snap_groups.items():
            snap_date = key.split("|")[0]
            if snap_date >= sf.subscription_date[:7]:
                for es in group:
                    if es.shareholder_name == sf.subscriber_name:
                        found = True
                        if sf.shares_subscribed and es.shares_held:
                            diff = es.shares_held - sf.shares_subscribed
                            st = "待复核" if abs(diff) > 0.01 else "PASS"
                            dt = "认购数 vs 存量持股数"
                            if st == "待复核":
                                dt += " ←待复核"
                            log_cross(company, "", sf.subscription_date,
                                      f"{sf.subscriber_name} (认缴→存量)",
                                      None, None, sf.shares_subscribed,
                                      sf.shares_subscribed, es.shares_held, diff,
                                      st, dt)
                        break
                if found:
                    break

    # 汇总
    critical = [i for i in issues if "schema" in str(i).lower() or "FAIL" in str(i) or "为空" in str(i)]
    status = "FAIL" if critical else ("WARN" if issues else "PASS")
    return status, len(sub_flows), len(eq_snaps), issues


def main():
    print("=" * 60)
    print("JSONL 校验 + 详细 Cross-Check")
    print("=" * 60)

    files = sorted(JSONL_DIR.glob("*.jsonl"))
    if not files:
        print("无 JSONL 文件"); sys.exit(1)

    all_ok = all_warn = all_fail = 0
    total_sub = total_eq = 0

    for f in files:
        status, n_sub, n_eq, issues = validate_file(f)
        total_sub += n_sub
        total_eq += n_eq
        if status == "PASS":
            all_ok += 1
        elif status == "WARN":
            all_warn += 1
        else:
            all_fail += 1
        print(f"  [{status}] {f.stem}: {n_sub} flows + {n_eq} snapshots | {len(issues)} issues")
        for iss in issues[:4]:
            print(f"    - {iss}")

    print(f"\n{'='*60}")
    print(f"汇总: {all_ok} PASS / {all_warn} WARN / {all_fail} FAIL")
    print(f"认缴流量: {total_sub} 条, 股权存量: {total_eq} 条")
    print(f"{'='*60}")

    now = datetime.now()

    # schema_validation_log.csv
    sl_path = LOG_DIR / "schema_validation_log.csv"
    with open(sl_path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["company", "record_type", "check_type", "status", "detail"])
        w.writeheader()
        w.writerows(_schema_rows)
    print(f"\nSchema 日志: {sl_path} ({len(_schema_rows)} 行)")

    # cross_check_summary.csv
    cc_path = LOG_DIR / "cross_check_summary.csv"
    with open(cc_path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "company", "snapshot_date_from", "snapshot_date_to", "shareholder_name",
            "previous_shares", "previous_capital", "subscription_change",
            "expected_shares", "pdf_disclosed_shares", "difference", "status", "detail"
        ])
        w.writeheader()
        w.writerows(_cross_rows)
    print(f"Cross-check: {cc_path} ({len(_cross_rows)} 行)")

    # 统计
    diff_rows = [r for r in _cross_rows if r["difference"] and float(r["difference"]) != 0]
    print(f"其中差额非零行: {len(diff_rows)}")
    for dr in diff_rows[:5]:
        print(f"  {dr['company']} {dr['shareholder_name']}: "
              f"prev={dr['previous_shares']} change={dr['subscription_change']} "
              f"expected={dr['expected_shares']} pdf={dr['pdf_disclosed_shares']} diff={dr['difference']}")

    return 0 if all_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
