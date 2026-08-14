#!/usr/bin/env python3
"""
Week 9 PE/VC-focused investor evaluator.

Protocol (Q16-Q20):
- Main investor metric includes evidence-backed institutional investors in PE/VC/CVC/
  strategic/government-guided/broker-direct-investment financing events.
- Excludes founders/controllers/natural persons/employee platforms/internal restructuring.
- Uses data/gold_standard/融资事件总表.jsonl investor_type as the evidence-backed event label.
- Evaluates subscription_flow investors only (consistent with week8/evaluate_investors.py v1).
- Entity identity is separate from amount/shares/price field accuracy.
- Canonical aliases are auditable and conservative.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]

PEVC_TYPE_PATTERNS = (
    "PE", "VC", "CVC", "产业资本", "战略投资", "战略资本",
    "券商直投", "政府引导基金", "国有资本", "创投", "私募",
)

EXCLUDED_TYPE_PATTERNS = (
    "自然人", "控股股东", "实际控制人", "员工持股平台", "其他",
)

INSTITUTION_MARKERS = (
    "公司", "基金", "合伙", "企业", "中心", "投资", "资本", "创投",
    "FUND", "LIMITED", "LLC", "L.P.", "LP",
)

# Auditable aliases seen/defined in the prospectus-development corpus.
# Key/value are normalized later; aliases map to one canonical legal/entity identity.
ALIAS_GROUPS = [
    ["深圳市创新投资集团有限公司", "深创投"],
    ["上海复星惟盈股权投资基金合伙企业(有限合伙)", "复星惟盈"],
    ["上海金浦临港智能科技股权投资基金合伙企业(有限合伙)", "金浦临港基金", "金浦临港"],
    ["上海金浦科技创业股权投资基金合伙企业(有限合伙)", "金浦科创基金", "金浦科创"],
    ["深圳市稳正景明创业投资企业(有限合伙)", "稳正景明"],
    ["深圳市稳正长泽创业投资企业(有限合伙)", "长泽创投", "稳正长泽"],
    ["武汉力源信息技术股份有限公司", "力源信息"],
    ["丰利财富(北京)国际资本管理股份有限公司", "丰利财富"],
    ["昆山红土高新创业投资有限公司", "昆山红土"],
    ["镇江红土创业投资有限公司", "镇江红土"],
    ["富海深湾(深圳)移动创新私募创业投资基金合伙企业(有限合伙)", "富海深湾"],
    ["中科贵银(贵州)创业投资中心(有限合伙)", "中科贵银"],
    ["厦门西堤股权投资合伙企业(有限合伙)", "厦门西堤", "厦门西"],
    ["国药中生(上海)生物股权投资基金合伙企业(有限合伙)", "国药中生"],
    ["国药二期(上海)生物医药投资中心(有限合伙)", "国药二期"],
    ["圣成投资管理(上海)有限公司", "圣成投资"],
    ["圣祁投资管理(上海)有限公司", "圣祁投资"],
]

def norm(s: str) -> str:
    s = str(s or "").strip().upper()
    s = s.replace("（", "(").replace("）", ")")
    s = re.sub(r"[\s\u3000]+", "", s)
    s = s.strip("，。；、,;:")
    return s

ALIAS_TO_CANON = {}
for group in ALIAS_GROUPS:
    canon = norm(group[0])
    for x in group:
        ALIAS_TO_CANON[norm(x)] = canon

def canonical(s: str) -> str:
    n = norm(s)
    if n in ALIAS_TO_CANON:
        return ALIAS_TO_CANON[n]
    # Conservative legal-form cleanup only for comparison fallback.
    return n

def institution_like(name: str) -> bool:
    n = norm(name)
    if not n or n == "（待识别）":
        return False
    return any(m in n for m in INSTITUTION_MARKERS)

def pevc_type(label: str) -> bool:
    t = str(label or "").upper()
    if any(x.upper() in t for x in EXCLUDED_TYPE_PATTERNS):
        return False
    return any(x.upper() in t for x in PEVC_TYPE_PATTERNS)

def date_compatible(gold_date: str, event_date: str) -> bool:
    g, e = str(gold_date or ""), str(event_date or "")
    if not g or not e:
        return False
    # Development-set relaxed date compatibility: year-month is sufficient.
    return g[:7] == e[:7]

def load_pevc_event_keys(master_path: Path):
    rows = []
    for line in master_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if pevc_type(r.get("investor_type")):
            rows.append(r)
    return rows

def row_in_pevc_event(row, master_rows) -> bool:
    code = row.get("stock_code", "")
    date = row.get("event_date", "")
    typ = row.get("event_type", "")
    for m in master_rows:
        if str(m.get("stock_code")) != str(code):
            continue
        if not date_compatible(date, m.get("date")):
            continue
        # Main investor evaluator is subscription-flow oriented: A/C.
        # Master table may encode C; allow exact type where available.
        mt = str(m.get("type", ""))
        if typ and mt and typ != mt:
            continue
        return True
    return False

def names_match(g, a):
    ng, na = canonical(g), canonical(a)
    if not ng or not na:
        return False
    if ng == na:
        return True, "canonical_exact"
    # Conservative containment only for institution names, not arbitrary 2-char strings.
    if institution_like(g) and institution_like(a) and min(len(ng), len(na)) >= 4:
        if ng in na or na in ng:
            return True, "institution_containment"
    return False, ""

def within_tol(gold, auto, tol=0.005):
    if gold in (None, ""):
        return None
    if auto in (None, ""):
        return False
    try:
        gv = float(str(gold).replace(",", ""))
        av = float(str(auto).replace(",", ""))
    except Exception:
        return False
    if gv == 0:
        return av == 0
    return abs(av - gv) / abs(gv) <= tol

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--details", type=Path,
                    default=PROJECT / "week9/stage3/investor_eval/investor_eval_details.csv")
    ap.add_argument("--master", type=Path,
                    default=PROJECT / "data/gold_standard/融资事件总表.jsonl")
    ap.add_argument("--out", type=Path,
                    default=PROJECT / "week9/pevc_eval")
    args = ap.parse_args()

    if not args.details.exists():
        raise SystemExit(f"Missing details: {args.details}")
    if not args.master.exists():
        raise SystemExit(f"Missing master table: {args.master}")

    master = load_pevc_event_keys(args.master)

    with args.details.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    gold = [
        r for r in rows
        if r.get("role") == "gold"
        and row_in_pevc_event(r, master)
        and institution_like(r.get("subscriber_name", ""))
    ]
    auto = [
        r for r in rows
        if r.get("role") == "auto"
        and row_in_pevc_event(r, master)
        and institution_like(r.get("subscriber_name", ""))
        and r.get("subscriber_name") != "（待识别）"
    ]

    # Match only within same company + event date(month-compatible) + type.
    used_auto = set()
    matches = []
    for gi, g in enumerate(gold):
        best = None
        for ai, a in enumerate(auto):
            if ai in used_auto:
                continue
            if g["stock_code"] != a["stock_code"] or g["event_type"] != a["event_type"]:
                continue
            if not date_compatible(g["event_date"], a["event_date"]):
                continue
            ok, method = names_match(g["subscriber_name"], a["subscriber_name"])
            if ok:
                best = (ai, method)
                if method == "canonical_exact":
                    break
        if best:
            ai, method = best
            used_auto.add(ai)
            matches.append((gi, ai, method))

    tp = len(matches)
    fp = len(auto) - tp
    fn = len(gold) - tp
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * precision * recall / (precision + recall) if precision and recall else None

    # Independent field metrics on matched PE/VC identities.
    field_stats = {}
    for fld, label in [("amount", "amount"), ("shares", "shares"), ("price", "price")]:
        denom = correct = missing = 0
        for gi, ai, _ in matches:
            g, a = gold[gi], auto[ai]
            cmp_ = within_tol(g.get(fld), a.get(fld))
            if cmp_ is not None:
                denom += 1
                if cmp_:
                    correct += 1
            if a.get(fld) in (None, ""):
                missing += 1
        field_stats[f"{label}_accuracy"] = correct / denom if denom else None
        field_stats[f"{label}_missing_rate_matched"] = missing / tp if tp else None

    match_by_g = {gi: (ai, method) for gi, ai, method in matches}
    match_by_a = {ai: (gi, method) for gi, ai, method in matches}
    detail_out = []

    for gi, g in enumerate(gold):
        if gi in match_by_g:
            ai, method = match_by_g[gi]
            a = auto[ai]
            status = "TP"
            matched = a["subscriber_name"]
        else:
            method, status, matched = "", "FN", ""
        detail_out.append({
            "role": "gold", "status": status,
            "stock_code": g["stock_code"], "event_date": g["event_date"],
            "event_type": g["event_type"],
            "raw_name": g["subscriber_name"],
            "canonical_name": canonical(g["subscriber_name"]),
            "matched_name": matched, "match_method": method,
            "amount": g.get("amount",""), "shares": g.get("shares",""), "price": g.get("price",""),
        })

    for ai, a in enumerate(auto):
        if ai in match_by_a:
            gi, method = match_by_a[ai]
            g = gold[gi]
            status, matched = "TP", g["subscriber_name"]
        else:
            method, status, matched = "", "FP", ""
        detail_out.append({
            "role": "auto", "status": status,
            "stock_code": a["stock_code"], "event_date": a["event_date"],
            "event_type": a["event_type"],
            "raw_name": a["subscriber_name"],
            "canonical_name": canonical(a["subscriber_name"]),
            "matched_name": matched, "match_method": method,
            "amount": a.get("amount",""), "shares": a.get("shares",""), "price": a.get("price",""),
        })

    summary = {
        "protocol": {
            "scope": "PE/VC-focused institutional investors",
            "evidence_source": str(args.master),
            "included_type_patterns": PEVC_TYPE_PATTERNS,
            "excluded_type_patterns": EXCLUDED_TYPE_PATTERNS,
            "entity_normalization": "auditable alias map + conservative institution containment",
            "date_match": "same year-month on dev set",
            "source_details": str(args.details),
        },
        "overall": {
            "gold_pevc_investors": len(gold),
            "auto_pevc_investors": len(auto),
            "matched": tp,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            **field_stats,
        },
    }

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "pevc_eval_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (args.out / "pevc_eval_details.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(detail_out[0].keys()))
        w.writeheader()
        w.writerows(detail_out)

    def pct(v):
        return "N/A" if v is None else f"{v:.2%}"

    print("========================================")
    print(" Week 9 PE/VC-focused Evaluation")
    print("========================================")
    print(f"Gold PE/VC investors : {len(gold)}")
    print(f"Auto PE/VC investors : {len(auto)}")
    print(f"Matched              : {tp}")
    print(f"Precision            : {pct(precision)}")
    print(f"Recall               : {pct(recall)}")
    print(f"F1                   : {pct(f1)}")
    print()
    print(f"Amount accuracy      : {pct(field_stats['amount_accuracy'])}")
    print(f"Shares accuracy      : {pct(field_stats['shares_accuracy'])}")
    print(f"Price accuracy       : {pct(field_stats['price_accuracy'])}")
    print()
    print("PE/VC Investor F1 >=90%:", "PASS" if f1 is not None and f1 >= .90 else "FAIL")
    print(f"Outputs: {args.out}")

if __name__ == "__main__":
    main()
