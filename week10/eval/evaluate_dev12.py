#!/usr/bin/env python3
"""Week 10 Stage 5D — evaluate cross-board extractor vs dev12_gold_draft.csv."""

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "week10" / "eval"

GOLD_CSV = EVAL / "dev12_gold_draft.csv"
XBOARD_DIR = EVAL / "dev12_xboard"

OUT_SUMMARY = EVAL / "dev12_xboard_summary.json"
OUT_DETAIL = EVAL / "dev12_xboard_details.csv"

DEV12 = [
    "001286", "001400", "301358", "301536", "301603", "301662",
    "603307", "603312", "920002", "920008", "920066", "920363",
]


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


# gold
with GOLD_CSV.open(encoding="utf-8-sig") as f:
    gold = [
        r for r in csv.DictReader(f)
        if str(r.get("include_pevc", "")).strip()
        in {"是", "1", "true", "True", "yes", "YES"}
    ]

# auto (cross-board extractor output)
auto = []
for code in DEV12:
    p = XBOARD_DIR / f"{code}_subscription_flow.jsonl"
    if not p.exists():
        continue
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            auto.append(json.loads(line))

G = {key(r): r for r in gold}
A = {key(r): r for r in auto}
gkeys = set(G)
akeys = set(A)

TP = gkeys & akeys
FP = akeys - gkeys
FN = gkeys - akeys
tp, fp, fn = len(TP), len(FP), len(FN)

precision = tp / (tp + fp) if tp + fp else 0
recall = tp / (tp + fn) if tp + fn else 0
f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0

print("=" * 64)
print("Week 10 Stage 5D — DEV 12 cross-board extractor evaluation")
print("=" * 64)
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
for code in DEV12:
    gg = {x for x in gkeys if x[0] == code}
    aa = {x for x in akeys if x[0] == code}
    t = len(gg & aa)
    fpos = len(aa - gg)
    fneg = len(gg - aa)
    p = t / (t + fpos) if t + fpos else 0
    r = t / (t + fneg) if t + fneg else 0
    ff = 2 * p * r / (p + r) if p + r else 0
    per_company[code] = {"gold": len(gg), "auto": len(aa), "tp": t,
                         "fp": fpos, "fn": fneg, "precision": p,
                         "recall": r, "f1": ff}
    print(f"{code}  Gold={len(gg):2d} Auto={len(aa):2d} TP={t:2d} "
          f"FP={fpos:2d} FN={fneg:2d}  P={p:.0%} R={r:.0%} F1={ff:.0%}")

# details
details = []
for k in sorted(TP):
    details.append({"status": "TP", "stock_code": k[0], "subscription_date": k[1],
                    "event_context": k[2], "subscriber_name": k[3]})
for k in sorted(FP):
    details.append({"status": "FP", "stock_code": k[0], "subscription_date": k[1],
                    "event_context": k[2], "subscriber_name": k[3]})
for k in sorted(FN):
    details.append({"status": "FN", "stock_code": k[0], "subscription_date": k[1],
                    "event_context": k[2], "subscriber_name": k[3]})

with OUT_DETAIL.open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=["status", "stock_code", "subscription_date",
                                      "event_context", "subscriber_name"])
    w.writeheader()
    w.writerows(details)

summary = {
    "gold_pevc": len(G), "auto_pevc": len(A), "tp": tp, "fp": fp, "fn": fn,
    "precision": precision, "recall": recall, "f1": f1,
    "per_company": per_company,
}
OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                       encoding="utf-8")

print()
print("===== FN (missed) =====")
for k in sorted(FN):
    print(" ", k[0], k[1], k[2], k[3])
print()
print("===== FP (spurious) =====")
for k in sorted(FP):
    print(" ", k[0], k[1], k[2], k[3])
print()
print("Outputs:", OUT_SUMMARY.relative_to(ROOT), OUT_DETAIL.relative_to(ROOT))
