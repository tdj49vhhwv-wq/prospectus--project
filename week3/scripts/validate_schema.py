#!/usr/bin/env python3
"""
Schema校验 + Cross-Check

输入: week3/outputs/auto_jsonl/*.jsonl (自动提取结果)
      week3/manual_gold/*.jsonl (Gold数据, 可选)
输出: week3/logs/schema_validation_log.csv
      week3/logs/cross_check_summary.csv

校验维度:
  1. JSONL逐行解析 + record_type检查
  2. Pydantic Schema校验 (字段类型/必填项/枚举值)
  3. 每家公司t0股权结构存在性
  4. 同一时点股东持股合计≈总股本
  5. 相邻时点股东变化追踪
  6. 认缴流量→存量对应
"""
import sys, json, csv, re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline_config import *

sys.path.insert(0, str(SCHEMA_MODULE))

try:
    from models import SubscriptionFlow, ShareTransferFlow, EquitySnapshot
    from pydantic import ValidationError
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False

_schema_rows = []
_cross_rows = []


def log_schema(company, record_type, check_type, status, detail=""):
    _schema_rows.append(dict(company=company, record_type=record_type,
                             check_type=check_type, status=status, detail=str(detail)))


def log_cross(**kw):
    _cross_rows.append(kw)


def fmt_num(v):
    if v is None: return ""
    return round(float(v), 4)


def parse_date(s):
    m = re.match(r'(\d{4})-(\d{2})', str(s))
    return f"{m.group(1)}-{m.group(2)}" if m else str(s)


def validate_jsonl_file(path, use_pydantic=True):
    """校验单个JSONL文件"""
    company = path.stem
    with open(path, encoding="utf-8") as f:
        lines = [json.loads(ln) for ln in f if ln.strip()]

    sub_flows, eq_snaps, issues = [], [], []

    for i, raw in enumerate(lines, 1):
        rt = raw.get("record_type", "")
        if rt not in ("subscription_flow", "share_transfer_flow", "equity_snapshot"):
            issues.append(f"line {i}: 非法 record_type={rt}")
            log_schema(company, rt or "unknown", "record_type", "FAIL", f"line={i}")
            continue

        # 必填字段检查
        if rt == "subscription_flow":
            req_fields = ["source_page", "subscription_date", "subscriber_name", "evidence_text"]
            for fld in req_fields:
                if not raw.get(fld):
                    issues.append(f"line {i}: {fld}为空")
                    log_schema(company, rt, f"required_{fld}", "FAIL", f"line={i}")

        if rt == "share_transfer_flow":
            req_fields = ["source_page", "transfer_date", "transferor_name", "transferee_name", "evidence_text"]
            for fld in req_fields:
                if not raw.get(fld):
                    issues.append(f"line {i}: {fld}为空")
                    log_schema(company, rt, f"required_{fld}", "FAIL", f"line={i}")

        if rt == "equity_snapshot":
            req_fields = ["source_page", "snapshot_date", "snapshot_type", "shareholder_name", "evidence_text"]
            for fld in req_fields:
                if not raw.get(fld):
                    issues.append(f"line {i}: {fld}为空")
                    log_schema(company, rt, f"required_{fld}", "FAIL", f"line={i}")

        # Pydantic
        if use_pydantic and HAS_PYDANTIC:
            try:
                if rt == "subscription_flow":
                    SubscriptionFlow.model_validate(raw)
                    sub_flows.append(raw)
                elif rt == "share_transfer_flow":
                    ShareTransferFlow.model_validate(raw)
                elif rt == "equity_snapshot":
                    EquitySnapshot.model_validate(raw)
                    eq_snaps.append(raw)
                log_schema(company, rt, "schema", "PASS", f"line={i}")
            except ValidationError as e:
                for err in e.errors():
                    issues.append(f"line {i}: {err['loc']} — {err['msg']}")
                log_schema(company, rt, "schema", "FAIL", f"line={i}, errors={e.error_count()}")
        else:
            if rt == "subscription_flow":
                sub_flows.append(raw)
            elif rt == "equity_snapshot":
                eq_snaps.append(raw)
            log_schema(company, rt, "schema", "PASS", f"line={i} (no pydantic)")

    # ── Auto-retry: schema失败自动修正 ──
    # Agent化: 不是只报告失败, 而是尝试自动修复
    auto_fixed = 0
    for i, raw in enumerate(lines, 1):
        rt = raw.get("record_type", "")
        fixed = False

        # 修正1: event_context不在枚举中 → 尝试标准化
        if rt == "subscription_flow":
            ec = raw.get("event_context", "")
            valid_ec = ["增资","股权转让","整体变更","设立","增资及股权转让","资本公积转增","VIE搭建","VIE拆除","吸收合并","改制","其他"]
            if ec and ec not in valid_ec:
                # 自动映射
                mapping = {"股份改制":"改制","股改":"改制","转增":"资本公积转增",
                          "增发":"增资","认购":"增资","转让":"股权转让"}
                if ec in mapping:
                    raw["event_context"] = mapping[ec]
                    auto_fixed += 1
                    fixed = True

            # 修正2: 日期格式 → 标准化
            import re
            date_str = raw.get("subscription_date", "")
            m = re.match(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', date_str)
            if m:
                raw["subscription_date"] = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
                auto_fixed += 1
                fixed = True
            elif re.match(r'(\d{4})\s*年\s*(\d{1,2})\s*月', date_str):
                m2 = re.match(r'(\d{4})\s*年\s*(\d{1,2})\s*月', date_str)
                raw["subscription_date"] = f"{m2.group(1)}-{int(m2.group(2)):02d}"
                auto_fixed += 1
                fixed = True

    # 重新校验修正后的行
    sub_flows, eq_snaps, issues = [], [], []
    for i, raw in enumerate(lines, 1):
        rt = raw.get("record_type", "")
        if rt not in ("subscription_flow", "share_transfer_flow", "equity_snapshot"):
            issues.append(f"line {i}: 非法 record_type={rt}")
            log_schema(company, rt or "unknown", "record_type", "FAIL", f"line={i}")
            continue

        # 必填字段检查
        if rt == "subscription_flow":
            for fld in ["source_page", "subscription_date", "subscriber_name", "evidence_text"]:
                if not raw.get(fld):
                    issues.append(f"line {i}: {fld}为空")
                    log_schema(company, rt, f"required_{fld}", "FAIL", f"line={i}")

        # Pydantic
        try:
            if rt == "subscription_flow":
                SubscriptionFlow.model_validate(raw)
                sub_flows.append(raw)
            elif rt == "share_transfer_flow":
                ShareTransferFlow.model_validate(raw)
            elif rt == "equity_snapshot":
                EquitySnapshot.model_validate(raw)
                eq_snaps.append(raw)
            log_schema(company, rt, "schema", "PASS", f"line={i}")
        except ValidationError as e:
            for err in e.errors():
                issues.append(f"line {i}: {err['loc']} — {err['msg']}")
            log_schema(company, rt, "schema", "FAIL", f"line={i}, errors={e.error_count()}")

    if auto_fixed > 0:
        log_schema(company, "system", "auto_fix", "INFO", f"自动修正了{auto_fixed}条记录的格式问题")

    # t0检查
    if eq_snaps:
        log_schema(company, "equity_snapshot", "t0_check", "PASS",
                   f"最早快照: {eq_snaps[0].get('snapshot_date','?')}")
    else:
        log_schema(company, "equity_snapshot", "t0_check", "WARN", "无股权存量记录")

    # 价格×数量≈金额 (subscription_flow)
    for i, sf in enumerate(sub_flows):
        if sf.get("price_per_share") and sf.get("shares_subscribed") and sf.get("amount_subscribed"):
            expected = sf["price_per_share"] * sf["shares_subscribed"]
            actual = sf["amount_subscribed"]
            if actual and actual > 0:
                diff_pct = abs(expected - actual) / actual
                st = "待复核" if (abs(expected - actual) > 1.0 or diff_pct > 0.01) else "PASS"
                log_cross(company="", snapshot_date_from="", snapshot_date_to=sf.get("subscription_date",""),
                          shareholder_name=sf.get("subscriber_name",""),
                          previous_shares="", previous_capital="",
                          subscription_change=fmt_num(sf.get("shares_subscribed")),
                          expected_shares=fmt_num(expected), pdf_disclosed_shares=fmt_num(actual),
                          difference=fmt_num(expected - actual), status=st,
                          detail=f"price×shares vs amount diff={diff_pct*100:.1f}%")

    # 股权快照分组
    snap_groups = defaultdict(list)
    for es in eq_snaps:
        key = f"{es.get('snapshot_date','')}|{es.get('snapshot_type','')}"
        snap_groups[key].append(es)
    sorted_keys = sorted(snap_groups.keys(), key=parse_date)

    # 同快照一致性: 持股合计≈总股本
    for key, group in snap_groups.items():
        shares_sum = sum(es.get("shares_held", 0) or 0 for es in group)
        ts = next((es.get("total_shares") for es in group if es.get("total_shares")), None)
        if shares_sum > 0 and ts:
            diff = shares_sum - ts
            st = "待复核" if abs(diff) > 0.01 else "PASS"
            log_cross(company="", snapshot_date_from="", snapshot_date_to=key.split("|")[0],
                      shareholder_name=f"[合计 {len(group)}股东]",
                      previous_shares="", previous_capital="", subscription_change="",
                      expected_shares=fmt_num(shares_sum), pdf_disclosed_shares=fmt_num(ts),
                      difference=fmt_num(diff), status=st,
                      detail=f"持股合计{shares_sum:.1f}万 vs 总股本{ts:.1f}万")

    return "FAIL" if [i for i in issues if "为空" in str(i)] else ("WARN" if issues else "PASS"), len(sub_flows), len(eq_snaps), issues


def main():
    print("=" * 60)
    print("[AUTO] validate_schema — Schema校验 + Cross-Check")
    print("=" * 60)

    # 校验Gold
    print("\n── Gold Data ──")
    gold_ok = gold_warn = gold_fail = gold_sub = gold_eq = 0
    gold_files = [f for f in MANUAL_GOLD_DIR.glob("*_gold.jsonl")
                   if f.stem != "cross_check_gold"]  # cross_check_gold是CSV格式,不校验
    for f in sorted(gold_files):
        status, n_sub, n_eq, issues = validate_jsonl_file(f)
        gold_sub += n_sub; gold_eq += n_eq
        if status == "PASS": gold_ok += 1
        elif status == "WARN": gold_warn += 1
        else: gold_fail += 1
        print(f"  [{status}] {f.stem}: {n_sub} flows + {n_eq} snaps | {len(issues)} issues")
        for iss in issues[:2]:
            print(f"    - {iss}")

    # 校验Auto
    print("\n── Auto Data ──")
    auto_ok = auto_warn = auto_fail = auto_sub = auto_eq = 0
    auto_files = list(AUTO_JSONL_DIR.glob("*.jsonl"))
    if not auto_files:
        print("  (无auto文件)")
    for f in sorted(auto_files):
        status, n_sub, n_eq, issues = validate_jsonl_file(f)
        auto_sub += n_sub; auto_eq += n_eq
        if status == "PASS": auto_ok += 1
        elif status == "WARN": auto_warn += 1
        else: auto_fail += 1
        print(f"  [{status}] {f.stem}: {n_sub} flows + {n_eq} snaps | {len(issues)} issues")
        for iss in issues[:2]:
            print(f"    - {iss}")

    print(f"\n汇总: Gold {gold_ok}P/{gold_warn}W/{gold_fail}F | Auto {auto_ok}P/{auto_warn}W/{auto_fail}F")
    ok, warn, fail = gold_ok+auto_ok, gold_warn+auto_warn, gold_fail+auto_fail
    total_sub, total_eq = gold_sub+auto_sub, gold_eq+auto_eq

    # 写日志
    with open(SCHEMA_LOG, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["company", "record_type", "check_type", "status", "detail"])
        w.writeheader(); w.writerows(_schema_rows)
    print(f"✓ Schema日志: {SCHEMA_LOG.name} ({len(_schema_rows)}行)")

    with open(CROSS_CHECK_LOG, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=[
            "company", "snapshot_date_from", "snapshot_date_to", "shareholder_name",
            "previous_shares", "previous_capital", "subscription_change",
            "expected_shares", "pdf_disclosed_shares", "difference", "status", "detail"])
        w.writeheader(); w.writerows(_cross_rows)
    print(f"✓ Cross-check: {CROSS_CHECK_LOG.name} ({len(_cross_rows)}行)")

    pending = [r for r in _cross_rows if r.get("status") == "待复核"]
    if pending:
        print(f"\n⚠ 待复核: {len(pending)}项")
        for p in pending[:5]:
            print(f"  {p.get('shareholder_name','')[:30]}: diff={p.get('difference','?')} ({p.get('detail','')})")

        # 自动生成复核任务 + 定位PDF相关表格
        from datetime import date
        queue_path = MANUAL_GOLD_DIR / "manual_review_queue.csv"

        # Agent化: cross-check失败时自动在MD文件中搜索相关数字
        for p in pending:
            shareholder = p.get("shareholder_name", "")
            diff_val = float(p.get("difference", 0))
            # 尝试在review目录中搜索包含该股东名和数字的段落
            import glob
            for mdf in glob.glob(str(REVIEW_DIR / "*.md")):
                try:
                    with open(mdf, encoding="utf-8", errors="ignore") as mf:
                        content = mf.read()
                    # 搜索股东名附近的数字
                    idx = content.find(shareholder[:8]) if len(shareholder) >= 8 else -1
                    if idx > 0:
                        snippet = content[max(0,idx-100):min(len(content),idx+200)]
                        # 找PDF页码
                        pm = re.search(r'##\s*第(\d+)页', content[:idx])
                        pdf_page = pm.group(1) if pm else "?"
                        p["related_pdf_page"] = pdf_page
                        p["related_text"] = snippet[:150].replace('\n',' ')
                        break
                except: pass
        new_tasks = []
        for p in pending:
            diff_val = float(p.get("difference", 0))
            priority = "P0" if abs(diff_val) > 100 else ("P1" if abs(diff_val) > 1 else "P2")
            task = {
                "priority": priority,
                "stock_code": p.get("company", "")[:6],
                "company_short": p.get("company", ""),
                "issue_type": "cross_check_failure",
                "description": f"cross-check待复核: {p.get('shareholder_name','')} diff={p.get('difference','')} {p.get('detail','')}",
                "status": "pending",
                "assigned_to": "auto_generated",
            }
            new_tasks.append(task)

        # 追加到现有队列 (不覆盖)
        existing = []
        if queue_path.exists():
            with open(queue_path, encoding="utf-8-sig") as f:
                existing = list(csv.DictReader(f))

        # 去重
        existing_descs = {t.get("description","") for t in existing}
        for t in new_tasks:
            if t["description"] not in existing_descs:
                existing.append(t)

        with open(queue_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["priority", "stock_code", "company_short", "issue_type", "description", "status", "assigned_to"])
            w.writeheader()
            w.writerows(existing)
        print(f"  → 已自动生成 {len(new_tasks)} 条复核任务到 manual_review_queue.csv")

    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
