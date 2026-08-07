#!/usr/bin/env python3
"""事件级 Auto-vs-Gold 评价器（Week 8 首版）

口径见 week8/matching_spec.md：
- Gold 事件来自 data/gold_standard/subscription_flow_gold.jsonl 与
  share_transfer_flow_gold.jsonl；
- Auto 事件来自 week6/auto_output_md/*.jsonl（Markdown 候选管线输出）；
- 同一事件的多条投资人明细聚合成一条事件记录；
- 一对一贪心匹配；日期按 Gold 粒度比较；类型只比较顶层码。
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CONTEXT_MAP = {
    "设立": "E",
    "增资": "A",
    "整体变更": "B",
    "增资及股权转让": "C",
    "增资+转让": "C",
    "股权转让": "D",
    "资本公积转增": "F",
    "吸收合并": "G",
    "员工持股平台出资": "J",
    "员工激励": "J",
}


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def parse_date(date_str: str) -> tuple[int, int, int]:
    """返回 (year, month, day)，缺失部分用 0。"""
    if not date_str:
        return (0, 0, 0)
    parts = str(date_str).split("-")
    year = int(parts[0]) if len(parts) > 0 and parts[0] else 0
    month = int(parts[1]) if len(parts) > 1 and parts[1] else 0
    day = int(parts[2]) if len(parts) > 2 and parts[2] else 0
    return (year, month, day)


def date_type_of(date_str: str) -> str:
    parts = [p for p in str(date_str).split("-") if p]
    if len(parts) == 3:
        return "day"
    if len(parts) == 2:
        return "month"
    if len(parts) == 1:
        return "year"
    return "none"


def dates_compatible(gold_date: str, auto_date: str) -> bool:
    """按 Gold 的粒度比较：day 同日、month 同年同月、year 同年。"""
    g = parse_date(gold_date)
    a = parse_date(auto_date)
    g_type = date_type_of(gold_date)
    if g_type == "day":
        return a == g
    if g_type == "month":
        return a[0] == g[0] and a[1] == g[1]
    if g_type == "year":
        return a[0] == g[0]
    return False


def _event_from_rows(rows: list[dict], kind: str) -> dict:
    first = rows[0]
    if kind == "gold_share_transfer":
        date = first.get("transfer_date", "")
        context = first.get("transfer_type", "股权转让")
        type_code = "D"
    else:
        date = first.get("subscription_date", "") or first.get("transfer_date", "")
        context = first.get("event_context", "")
        type_code = CONTEXT_MAP.get(context, "X")
    return {
        "stock_code": first.get("stock_code", ""),
        "company_name": first.get("company_name", ""),
        "date": date,
        "date_type": date_type_of(date),
        "type_code": type_code,
        "context": context,
        "row_count": len(rows),
        "evidence": first.get("evidence_text", "")[:500],
        "source_page": first.get("source_page", ""),
        "kind": kind,
        "rows": rows,
    }


def build_gold_events(gold_dir: Path) -> list[dict]:
    events: list[dict] = []
    # 增资/设立/股改等：同 (公司, 日期, 事件类型) 的多投资人明细合并为一条事件
    sf_path = gold_dir / "subscription_flow_gold.jsonl"
    grouped: dict[tuple, list] = defaultdict(list)
    for r in load_jsonl(sf_path):
        key = (r.get("stock_code", ""), r.get("subscription_date", ""), r.get("event_context", ""))
        grouped[key].append(r)
    for rows in grouped.values():
        events.append(_event_from_rows(rows, "gold_subscription"))

    # 股权转让：每条转让明细本身是一条事件（转出方 → 受让方）
    st_path = gold_dir / "share_transfer_flow_gold.jsonl"
    for r in load_jsonl(st_path):
        events.append(_event_from_rows([r], "gold_share_transfer"))
    return events


def build_auto_events(auto_dir: Path) -> list[dict]:
    events: list[dict] = []
    grouped: dict[tuple, list] = defaultdict(list)
    for path in sorted(auto_dir.glob("*_subscription_flow.jsonl")):
        for r in load_jsonl(path):
            key = (r.get("stock_code", ""), r.get("subscription_date", ""), r.get("event_context", ""))
            grouped[key].append(r)
    for rows in grouped.values():
        events.append(_event_from_rows(rows, "auto"))
    return events


def match_events(gold_events: list[dict], auto_events: list[dict]) -> tuple[dict, dict]:
    """一对一贪心匹配，返回 (gold 结果, auto 结果)。"""
    gold_result: dict[int, dict] = {}
    auto_result: dict[int, dict] = {i: {"event": ae, "status": "FP", "matched_gold_id": None}
                                    for i, ae in enumerate(auto_events)}
    used_auto: set[int] = set()

    # 全局排序，保证跨公司索引不撞车
    auto_order = sorted(range(len(auto_events)),
                        key=lambda i: (auto_events[i]["stock_code"], auto_events[i]["date"],
                                       auto_events[i]["type_code"], auto_events[i]["context"]))

    for gi, ge in sorted(enumerate(gold_events), key=lambda x: (x[1]["stock_code"], x[1]["date"], x[1]["type_code"])):
        matched = None
        for ai in auto_order:
            if ai in used_auto:
                continue
            ae = auto_events[ai]
            if ae["stock_code"] != ge["stock_code"]:
                continue
            if ae["type_code"] != ge["type_code"]:
                continue
            if not dates_compatible(ge["date"], ae["date"]):
                continue
            matched = ai
            break
        if matched is not None:
            used_auto.add(matched)
            gold_result[gi] = {"event": ge, "status": "TP", "matched_auto_id": matched}
            auto_result[matched] = {"event": auto_events[matched], "status": "TP", "matched_gold_id": gi}
        else:
            gold_result[gi] = {"event": ge, "status": "FN", "matched_auto_id": None}

    return gold_result, auto_result


def prf(tp: int, fp: int, fn: int) -> tuple[float | None, float | None, float | None]:
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f1 = 2 * p * r / (p + r) if p is not None and r is not None and p + r else None
    return p, r, f1


def fmt(v: float | None) -> str:
    return "N/A" if v is None else f"{v:.4f}"


def summarize(gold_result: dict, auto_result: dict) -> dict:
    def stats(ge_filter=None, ae_filter=None) -> dict:
        tp = sum(1 for r in gold_result.values() if r["status"] == "TP" and (ge_filter is None or ge_filter(r["event"])))
        fn = sum(1 for r in gold_result.values() if r["status"] == "FN" and (ge_filter is None or ge_filter(r["event"])))
        fp = sum(1 for r in auto_result.values() if r["status"] == "FP" and (ae_filter is None or ae_filter(r["event"])))
        p, r, f1 = prf(tp, fp, fn)
        return {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r, "f1": f1}

    summary = {"overall": stats()}
    companies = sorted({e["stock_code"] for e in [r["event"] for r in gold_result.values()] +
                        [r["event"] for r in auto_result.values()]})
    summary["by_company"] = {
        c: stats(
            lambda e, c=c: e["stock_code"] == c,
            lambda e, c=c: e["stock_code"] == c,
        )
        for c in companies
    }
    types = sorted({e["type_code"] for e in [r["event"] for r in gold_result.values()] +
                    [r["event"] for r in auto_result.values()]})
    summary["by_type"] = {
        t: stats(
            lambda e, t=t: e["type_code"] == t,
            lambda e, t=t: e["type_code"] == t,
        )
        for t in types
    }
    return summary


def write_details(gold_result: dict, auto_result: dict, out_csv: Path) -> None:
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["role", "stock_code", "date", "date_type", "type_code", "context",
                         "row_count", "status", "matched_id", "source_page", "evidence"])
        for gi, r in sorted(gold_result.items()):
            e = r["event"]
            writer.writerow(["gold", e["stock_code"], e["date"], e["date_type"], e["type_code"],
                             e["context"], e["row_count"], r["status"], r["matched_auto_id"],
                             e["source_page"], e["evidence"].strip()])
        for ai, r in sorted(auto_result.items()):
            e = r["event"]
            writer.writerow(["auto", e["stock_code"], e["date"], e["date_type"], e["type_code"],
                             e["context"], e["row_count"], r["status"], r["matched_gold_id"],
                             e["source_page"], e["evidence"].strip()])


def main() -> None:
    parser = argparse.ArgumentParser(description="事件级 Auto-vs-Gold 评价器")
    parser.add_argument("--gold", type=Path, default=PROJECT_ROOT / "data" / "gold_standard")
    parser.add_argument("--auto", type=Path, default=PROJECT_ROOT / "week6" / "auto_output_md" / "validated")
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT / "week8" / "event_eval")
    args = parser.parse_args()

    gold_events = build_gold_events(args.gold)
    auto_events = build_auto_events(args.auto)
    gold_result, auto_result = match_events(gold_events, auto_events)
    summary = summarize(gold_result, auto_result)
    summary["gold_event_count"] = len(gold_events)
    summary["auto_event_count"] = len(auto_events)
    summary["auto_missing_date_events"] = sum(1 for e in auto_events if e["date_type"] == "none")

    args.out.mkdir(parents=True, exist_ok=True)
    write_details(gold_result, auto_result, args.out / "event_eval_details.csv")
    with open(args.out / "event_eval_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"Gold 事件: {len(gold_events)}  Auto 事件: {len(auto_events)}  "
          f"Auto 缺日期事件: {summary['auto_missing_date_events']}")
    print("Overall:", {k: (fmt(v) if k not in ("tp", "fp", "fn") else v)
                       for k, v in summary["overall"].items()})
    print("按公司:")
    for code, s in summary["by_company"].items():
        print(f"  {code}: TP={s['tp']} FP={s['fp']} FN={s['fn']} "
              f"P={fmt(s['precision'])} R={fmt(s['recall'])} F1={fmt(s['f1'])}")
    print("按类型:")
    for t, s in summary["by_type"].items():
        print(f"  {t}: TP={s['tp']} FP={s['fp']} FN={s['fn']} "
              f"P={fmt(s['precision'])} R={fmt(s['recall'])} F1={fmt(s['f1'])}")
    print(f"明细: {args.out / 'event_eval_details.csv'}")


if __name__ == "__main__":
    main()
