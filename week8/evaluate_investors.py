#!/usr/bin/env python3
"""投资人明细级评价器（Week 8/9 提前执行）

口径（week8/matching_spec.md v1.1）：
- 先做事件级匹配（复用 evaluate_events.match_events，开发集开启
  --relax-gold-day-to-month）；
- 仅在 TP 事件内匹配投资人明细行（subscription_flow；股权转让 v1 暂不评价）；
- 名称先标准化，一对一贪心匹配；金额/股数/价格容差 0.5%；
- Gold 未披露字段不参与字段准确率；Auto 未披露字段计入缺失率。
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

from evaluate_events import (
    build_auto_events,
    build_gold_events,
    match_events,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def norm_name(name) -> str:
    if not name:
        return ""
    s = str(name).strip().upper()
    s = re.sub(r"[\s\u3000]+", "", s)
    return s.replace("（", "(").replace("）", ")")


def within_tol(gold, auto, tol=0.005):
    """数值容差；Gold 未披露返回 None，Auto 缺失返回 False。"""
    if gold is None:
        return None
    if auto is None:
        return False
    try:
        gv = float(str(gold).replace(",", ""))
        av = float(str(auto).replace(",", ""))
    except (TypeError, ValueError):
        return False
    if gv == 0:
        return av == 0
    return abs(av - gv) / abs(gv) <= tol


def names_equal(g, a) -> bool:
    return norm_name(g) == norm_name(a)


def names_fuzzy(g, a) -> bool:
    ng, na = norm_name(g), norm_name(a)
    return len(ng) >= 2 and len(na) >= 2 and (ng in na or na in ng)


def match_investor_rows(gold_rows, auto_rows):
    """事件内一对一贪心匹配投资人明细行，返回 [(gold_idx, auto_idx), ...]。"""
    gold_order = sorted(range(len(gold_rows)),
                        key=lambda i: (norm_name(gold_rows[i].get("subscriber_name", "")), i))
    auto_used = set()
    pairs = []
    for gi in gold_order:
        g = gold_rows[gi]
        best = None
        best_score = None
        for ai, a in enumerate(auto_rows):
            if ai in auto_used:
                continue
            if names_equal(g.get("subscriber_name"), a.get("subscriber_name")):
                score = 0
            elif names_fuzzy(g.get("subscriber_name"), a.get("subscriber_name")):
                score = 1
            else:
                continue
            amt_score = 0 if within_tol(g.get("amount_subscribed"), a.get("amount_subscribed")) else 2
            total = score + amt_score
            if best_score is None or total < best_score:
                best = ai
                best_score = total
        if best is not None:
            auto_used.add(best)
            pairs.append((gi, best))
    return pairs


FIELD_SHORT = {
    "amount_subscribed": "amount",
    "shares_subscribed": "shares",
    "price_per_share": "price",
}


def eval_event(gold_rows, auto_rows) -> dict:
    pairs = match_investor_rows(gold_rows, auto_rows)
    matched_auto = {ai for _, ai in pairs}
    stats = {
        "gold_rows": len(gold_rows),
        "auto_rows": len(auto_rows),
        "matched": len(pairs),
        "gold_unmatched": len(gold_rows) - len(pairs),
        "auto_unmatched": len(auto_rows) - len(matched_auto),
        "amount_correct": 0,
        "amount_denom": 0,
        "shares_correct": 0,
        "shares_denom": 0,
        "price_correct": 0,
        "price_denom": 0,
        "auto_missing_amount": 0,
        "auto_missing_shares": 0,
        "auto_missing_price": 0,
    }
    for ai in range(len(auto_rows)):
        if auto_rows[ai].get("amount_subscribed") is None:
            stats["auto_missing_amount"] += 1
        if auto_rows[ai].get("shares_subscribed") is None:
            stats["auto_missing_shares"] += 1
        if auto_rows[ai].get("price_per_share") is None:
            stats["auto_missing_price"] += 1
    for gi, ai in pairs:
        g, a = gold_rows[gi], auto_rows[ai]
        for field, short in FIELD_SHORT.items():
            cmp_ = within_tol(g.get(field), a.get(field))
            if cmp_ is not None:
                stats[f"{short}_denom"] += 1
                if cmp_:
                    stats[f"{short}_correct"] += 1
    return stats


def merge_stats(target: dict, add: dict) -> None:
    for k, v in add.items():
        target[k] = target.get(k, 0) + v


def summarize(stats: dict) -> dict:
    def rate(correct, denom):
        return (correct / denom) if denom else None

    return {
        "gold_investor_rows": stats["gold_rows"],
        "auto_investor_rows": stats["auto_rows"],
        "matched_investor_rows": stats["matched"],
        "investor_recall": rate(stats["matched"], stats["gold_rows"]),
        "investor_precision": rate(stats["matched"], stats["auto_rows"]),
        "amount_accuracy": rate(stats["amount_correct"], stats["amount_denom"]),
        "shares_accuracy": rate(stats["shares_correct"], stats["shares_denom"]),
        "price_accuracy": rate(stats["price_correct"], stats["price_denom"]),
        "auto_missing_amount_rate": rate(stats["auto_missing_amount"], stats["auto_rows"]),
        "auto_missing_shares_rate": rate(stats["auto_missing_shares"], stats["auto_rows"]),
        "auto_missing_price_rate": rate(stats["auto_missing_price"], stats["auto_rows"]),
    }


def fmt(v):
    return "N/A" if v is None else f"{v:.4f}"


def main() -> None:
    parser = argparse.ArgumentParser(description="投资人明细级评价器")
    parser.add_argument("--gold", type=Path, default=PROJECT_ROOT / "data" / "gold_standard")
    parser.add_argument("--auto", type=Path, default=PROJECT_ROOT / "week6" / "auto_output_md" / "validated")
    parser.add_argument("--relax-gold-day-to-month", action="store_true")
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT / "week8" / "investor_eval")
    args = parser.parse_args()

    gold_events = build_gold_events(args.gold)
    auto_events = build_auto_events(args.auto)
    gold_result, auto_result = match_events(gold_events, auto_events,
                                            relax_gold_day_to_month=args.relax_gold_day_to_month)

    overall = {k: 0 for k in (
        "gold_rows", "auto_rows", "matched", "gold_unmatched", "auto_unmatched",
        "amount_correct", "amount_denom", "shares_correct", "shares_denom",
        "price_correct", "price_denom",
        "auto_missing_amount", "auto_missing_shares", "auto_missing_price",
    )}
    by_company = {}
    details = []

    for gi, r in sorted(gold_result.items()):
        if r["status"] != "TP":
            continue
        ge = r["event"]
        ae = auto_events[r["matched_auto_id"]]
        gold_rows = [x for x in ge["rows"] if x.get("record_type") == "subscription_flow"]
        auto_rows = [x for x in ae["rows"] if x.get("event_context") != "股权转让"]
        if not gold_rows:
            continue
        stats = eval_event(gold_rows, auto_rows)
        merge_stats(overall, stats)
        by_company.setdefault(ge["stock_code"], {k: 0 for k in overall}).update(
            {k: v + by_company[ge["stock_code"]].get(k, 0) for k, v in stats.items()})

        pairs = match_investor_rows(gold_rows, auto_rows)
        matched_auto = {ai for _, ai in pairs}
        for gi2, g in enumerate(gold_rows):
            ai2 = next((ai for gi3, ai in pairs if gi3 == gi2), None)
            details.append({
                "stock_code": ge["stock_code"],
                "event_date": ge["date"],
                "event_type": ge["type_code"],
                "role": "gold",
                "subscriber_name": g.get("subscriber_name"),
                "amount": g.get("amount_subscribed"),
                "shares": g.get("shares_subscribed"),
                "price": g.get("price_per_share"),
                "status": "matched" if ai2 is not None else "unmatched",
                "matched_auto": auto_rows[ai2].get("subscriber_name") if ai2 is not None else "",
            })
        for ai2, a in enumerate(auto_rows):
            gi2 = next((gi3 for gi3, ai3 in pairs if ai3 == ai2), None)
            details.append({
                "stock_code": ge["stock_code"],
                "event_date": ge["date"],
                "event_type": ge["type_code"],
                "role": "auto",
                "subscriber_name": a.get("subscriber_name"),
                "amount": a.get("amount_subscribed"),
                "shares": a.get("shares_subscribed"),
                "price": a.get("price_per_share"),
                "status": "matched" if gi2 is not None else "unmatched",
                "matched_auto": gold_rows[gi2].get("subscriber_name") if gi2 is not None else "",
            })

    summary = {
        "overall": summarize(overall),
        "by_company": {code: summarize(s) for code, s in sorted(by_company.items())},
        "match_options": {"relax_gold_day_to_month": args.relax_gold_day_to_month},
    }

    args.out.mkdir(parents=True, exist_ok=True)
    with open(args.out / "investor_eval_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with open(args.out / "investor_eval_details.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(details[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(details)

    o = summary["overall"]
    print(f"TP 事件内投资人明细: Gold {o['gold_investor_rows']} / Auto {o['auto_investor_rows']} / "
          f"匹配 {o['matched_investor_rows']}")
    print(f"投资人 Recall={fmt(o['investor_recall'])} Precision={fmt(o['investor_precision'])}")
    print(f"字段准确率: 金额={fmt(o['amount_accuracy'])} 股数={fmt(o['shares_accuracy'])} 价格={fmt(o['price_accuracy'])}")
    print(f"Auto 缺失率: 金额={fmt(o['auto_missing_amount_rate'])} 股数={fmt(o['auto_missing_shares_rate'])} "
          f"价格={fmt(o['auto_missing_price_rate'])}")
    print(f"输出: {args.out}")


if __name__ == "__main__":
    main()
