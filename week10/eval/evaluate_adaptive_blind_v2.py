#!/usr/bin/env python3

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

AUTO = (
    ROOT
    / "week10"
    / "adaptive"
    / "final_v2"
    / "adaptive_blind_pevc_rows_v2.csv"
)

GOLD = (
    ROOT
    / "week9"
    / "blind_run1"
    / "blind_gold.csv"
)

BASELINE = (
    ROOT
    / "week9"
    / "blind_run1"
    / "blind_eval_summary.json"
)

V1 = (
    ROOT
    / "week10"
    / "eval"
    / "adaptive_blind_v1_summary.json"
)

OUT = (
    ROOT
    / "week10"
    / "eval"
    / "adaptive_blind_v2_summary.json"
)

DETAIL = (
    ROOT
    / "week10"
    / "eval"
    / "adaptive_blind_v2_details.csv"
)


def norm(x):
    s = str(x or "").strip().upper()
    s = s.replace("（", "(").replace("）", ")")
    s = re.sub(r"\s+", "", s)
    return s.strip("，。；、,;:")


def key(r):
    return (
        str(r.get("stock_code", "")).strip(),
        str(r.get("subscription_date", ""))[:7],
        str(r.get("event_context", "")).strip(),
        norm(r.get("subscriber_name", "")),
    )


with AUTO.open(
    encoding="utf-8-sig"
) as f:
    auto = list(csv.DictReader(f))


with GOLD.open(
    encoding="utf-8-sig"
) as f:

    gold = [
        r
        for r in csv.DictReader(f)
        if str(
            r.get("include_pevc", "")
        ).strip()
        in {
            "是",
            "1",
            "true",
            "True",
            "yes",
            "YES",
        }
    ]


G = {
    key(r): r
    for r in gold
}

A = {
    key(r): r
    for r in auto
}

gkeys = set(G)
akeys = set(A)

TP = gkeys & akeys
FP = akeys - gkeys
FN = gkeys - akeys

tp = len(TP)
fp = len(FP)
fn = len(FN)

precision = (
    tp / (tp + fp)
    if tp + fp
    else 0
)

recall = (
    tp / (tp + fn)
    if tp + fn
    else 0
)

f1 = (
    2 * precision * recall
    / (precision + recall)
    if precision + recall
    else 0
)


print()
print("=" * 60)
print(
    "Week 10 Adaptive v2 — Blind Evaluation"
)
print("=" * 60)

print(f"Gold PE/VC : {len(G)}")
print(f"Auto PE/VC : {len(A)}")
print(f"TP         : {tp}")
print(f"FP         : {fp}")
print(f"FN         : {fn}")
print(f"Precision  : {precision:.2%}")
print(f"Recall     : {recall:.2%}")
print(f"F1         : {f1:.2%}")


print()
print("===== BY COMPANY =====")

per_company = {}

for code in ["688795", "688802"]:

    gg = {
        x
        for x in gkeys
        if x[0] == code
    }

    aa = {
        x
        for x in akeys
        if x[0] == code
    }

    t = len(gg & aa)
    fpos = len(aa - gg)
    fneg = len(gg - aa)

    p = (
        t / (t + fpos)
        if t + fpos
        else 0
    )

    r = (
        t / (t + fneg)
        if t + fneg
        else 0
    )

    ff = (
        2 * p * r / (p + r)
        if p + r
        else 0
    )

    per_company[code] = {
        "gold": len(gg),
        "auto": len(aa),
        "tp": t,
        "fp": fpos,
        "fn": fneg,
        "precision": p,
        "recall": r,
        "f1": ff,
    }

    print(
        code,
        f"Gold={len(gg)}",
        f"Auto={len(aa)}",
        f"TP={t}",
        f"FP={fpos}",
        f"FN={fneg}",
        f"P={p:.2%}",
        f"R={r:.2%}",
        f"F1={ff:.2%}",
    )


baseline = json.loads(
    BASELINE.read_text(
        encoding="utf-8"
    )
)

v1 = json.loads(
    V1.read_text(
        encoding="utf-8"
    )
)


print()
print("===== THREE-WAY COMPARISON =====")

print(
    "                 Frozen       Adaptive v1   Adaptive v2"
)

print(
    f"TP             "
    f"{baseline['tp']:>8}       "
    f"{v1['tp']:>8}       "
    f"{tp:>8}"
)

print(
    f"FP             "
    f"{baseline['fp']:>8}       "
    f"{v1['fp']:>8}       "
    f"{fp:>8}"
)

print(
    f"FN             "
    f"{baseline['fn']:>8}       "
    f"{v1['fn']:>8}       "
    f"{fn:>8}"
)

print(
    f"Precision      "
    f"{baseline['precision']:>8.2%}       "
    f"{v1['precision']:>8.2%}       "
    f"{precision:>8.2%}"
)

print(
    f"Recall         "
    f"{baseline['recall']:>8.2%}       "
    f"{v1['recall']:>8.2%}       "
    f"{recall:>8.2%}"
)

print(
    f"F1             "
    f"{baseline['f1']:>8.2%}       "
    f"{v1['f1']:>8.2%}       "
    f"{f1:>8.2%}"
)


print()
print("===== V1 → V2 INCREMENT =====")

print(
    "ΔTP:",
    tp - v1["tp"]
)

print(
    "ΔFP:",
    fp - v1["fp"]
)

print(
    "ΔFN:",
    fn - v1["fn"]
)

print(
    "ΔRecall:",
    f"{recall - v1['recall']:+.2%}"
)

print(
    "ΔF1:",
    f"{f1 - v1['f1']:+.2%}"
)


details = []

for k in sorted(TP):
    details.append({
        "status": "TP",
        "stock_code": k[0],
        "subscription_date": k[1],
        "event_context": k[2],
        "subscriber_name": k[3],
    })

for k in sorted(FP):
    details.append({
        "status": "FP",
        "stock_code": k[0],
        "subscription_date": k[1],
        "event_context": k[2],
        "subscriber_name": k[3],
    })

for k in sorted(FN):
    details.append({
        "status": "FN",
        "stock_code": k[0],
        "subscription_date": k[1],
        "event_context": k[2],
        "subscriber_name": k[3],
    })


with DETAIL.open(
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:

    fields = [
        "status",
        "stock_code",
        "subscription_date",
        "event_context",
        "subscriber_name",
    ]

    w = csv.DictWriter(
        f,
        fieldnames=fields
    )

    w.writeheader()
    w.writerows(details)


summary = {
    "gold_pevc": len(G),
    "auto_pevc": len(A),
    "tp": tp,
    "fp": fp,
    "fn": fn,
    "precision": precision,
    "recall": recall,
    "f1": f1,
    "per_company": per_company,
    "baseline": baseline,
    "adaptive_v1": {
        "tp": v1["tp"],
        "fp": v1["fp"],
        "fn": v1["fn"],
        "precision": v1["precision"],
        "recall": v1["recall"],
        "f1": v1["f1"],
    },
}


OUT.write_text(
    json.dumps(
        summary,
        ensure_ascii=False,
        indent=2
    ),
    encoding="utf-8"
)


print()
print("Outputs:")
print(" ", OUT.relative_to(ROOT))
print(" ", DETAIL.relative_to(ROOT))
