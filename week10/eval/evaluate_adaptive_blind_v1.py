#!/usr/bin/env python3

import csv
import json
import re
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parents[2]

AUTO = (
    ROOT
    / "week10"
    / "adaptive"
    / "final_v1"
    / "adaptive_blind_pevc_rows.csv"
)

GOLD = (
    ROOT
    / "week9"
    / "blind_run1"
    / "blind_gold.csv"
)

BASE_SUMMARY = (
    ROOT
    / "week9"
    / "blind_run1"
    / "blind_eval_summary.json"
)

OUT_SUMMARY = (
    ROOT
    / "week10"
    / "eval"
    / "adaptive_blind_v1_summary.json"
)

OUT_DETAILS = (
    ROOT
    / "week10"
    / "eval"
    / "adaptive_blind_v1_details.csv"
)


def norm(x):
    s = str(x or "").strip().upper()
    s = s.replace("（", "(").replace("）", ")")
    s = re.sub(r"\s+", "", s)
    return s.strip("，。；、,;:")


def key(r):
    return (
        str(
            r.get("stock_code", "")
        ).strip(),

        str(
            r.get(
                "subscription_date",
                ""
            )
        )[:7],

        str(
            r.get(
                "event_context",
                ""
            )
        ).strip(),

        norm(
            r.get(
                "subscriber_name",
                ""
            )
        ),
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


G = {key(r): r for r in gold}
A = {key(r): r for r in auto}

gkeys = set(G)
akeys = set(A)

tp_keys = gkeys & akeys
fp_keys = akeys - gkeys
fn_keys = gkeys - akeys

tp = len(tp_keys)
fp = len(fp_keys)
fn = len(fn_keys)

p = tp / (tp + fp) if tp + fp else 0.0
r = tp / (tp + fn) if tp + fn else 0.0
f1 = (
    2 * p * r / (p + r)
    if p + r
    else 0.0
)


print()
print("=" * 56)
print(
    "Week 10 Adaptive v1 — Blind Evaluation"
)
print("=" * 56)

print(f"Gold PE/VC : {len(G)}")
print(f"Auto PE/VC : {len(A)}")
print(f"TP         : {tp}")
print(f"FP         : {fp}")
print(f"FN         : {fn}")
print(f"Precision  : {p:.2%}")
print(f"Recall     : {r:.2%}")
print(f"F1         : {f1:.2%}")


print()
print("===== BY COMPANY =====")

codes = sorted(
    {
        k[0]
        for k in gkeys | akeys
    }
)

per_company = {}

for code in codes:

    gg = {
        x for x in gkeys
        if x[0] == code
    }

    aa = {
        x for x in akeys
        if x[0] == code
    }

    t = len(gg & aa)
    fpos = len(aa - gg)
    fneg = len(gg - aa)

    pp = (
        t / (t + fpos)
        if t + fpos
        else 0
    )

    rr = (
        t / (t + fneg)
        if t + fneg
        else 0
    )

    ff = (
        2 * pp * rr / (pp + rr)
        if pp + rr
        else 0
    )

    per_company[code] = {
        "gold": len(gg),
        "auto": len(aa),
        "tp": t,
        "fp": fpos,
        "fn": fneg,
        "precision": pp,
        "recall": rr,
        "f1": ff,
    }

    print(
        code,
        f"Gold={len(gg)}",
        f"Auto={len(aa)}",
        f"TP={t}",
        f"FP={fpos}",
        f"FN={fneg}",
        f"P={pp:.2%}",
        f"R={rr:.2%}",
        f"F1={ff:.2%}",
    )


base = json.loads(
    BASE_SUMMARY.read_text(
        encoding="utf-8"
    )
)

print()
print("===== BASELINE → ADAPTIVE =====")

print(
    f"Precision: "
    f"{base['precision']:.2%}"
    f" → {p:.2%}"
)

print(
    f"Recall:    "
    f"{base['recall']:.2%}"
    f" → {r:.2%}"
)

print(
    f"F1:        "
    f"{base['f1']:.2%}"
    f" → {f1:.2%}"
)

print(
    f"TP:        "
    f"{base['tp']}"
    f" → {tp}"
)

print(
    f"FP:        "
    f"{base['fp']}"
    f" → {fp}"
)

print(
    f"FN:        "
    f"{base['fn']}"
    f" → {fn}"
)


details = []

for k in sorted(tp_keys):
    details.append({
        "status": "TP",
        "stock_code": k[0],
        "subscription_date": k[1],
        "event_context": k[2],
        "subscriber_name": k[3],
    })

for k in sorted(fp_keys):
    details.append({
        "status": "FP",
        "stock_code": k[0],
        "subscription_date": k[1],
        "event_context": k[2],
        "subscriber_name": k[3],
    })

for k in sorted(fn_keys):
    details.append({
        "status": "FN",
        "stock_code": k[0],
        "subscription_date": k[1],
        "event_context": k[2],
        "subscriber_name": k[3],
    })


with OUT_DETAILS.open(
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
    "precision": p,
    "recall": r,
    "f1": f1,
    "baseline": base,
    "per_company": per_company,
}


OUT_SUMMARY.write_text(
    json.dumps(
        summary,
        ensure_ascii=False,
        indent=2
    ),
    encoding="utf-8"
)


print()
print("Outputs:")
print(
    " ",
    OUT_SUMMARY.relative_to(ROOT)
)
print(
    " ",
    OUT_DETAILS.relative_to(ROOT)
)
