#!/usr/bin/env python3
"""Week 10 Stage 5D — generalized cross-board extractor evaluation.

Usable for DEV / VAL / BLIND: point it at a gold CSV, the extractor's JSONL
output dir, and the code list, and it emits per-company + aggregate F1 plus a
TP/FP/FN details CSV.

Usage:
  python3 evaluate_stage5d.py --gold dev12_gold_draft.csv \
      --pred-dir dev12_xboard --codes 001286 001400 ... --out dev12_xboard
"""

import argparse
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "week10" / "eval"


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


def load_gold(gold_csv, exclude_prelisting=False):
    """Load gold PE/VC rows.

    exclude_prelisting=True 时剔除 `disclosure_form == 'prelisting'`（挂牌前入股、
    时点未在招股书披露 → 不可恢复项），不计入 Recall 分母（阶段 0 边界规则）。
    """
    with Path(gold_csv).open(encoding="utf-8-sig") as f:
        rows = [
            r for r in csv.DictReader(f)
            if str(r.get("include_pevc", "")).strip()
            in {"是", "1", "true", "True", "yes", "YES"}
        ]
    if exclude_prelisting:
        rows = [
            r for r in rows
            if str(r.get("disclosure_form", "")).strip() != "prelisting"
        ]
    return rows


def load_auto(pred_dir, codes):
    auto = []
    for code in codes:
        p = Path(pred_dir) / f"{code}_subscription_flow.jsonl"
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                auto.append(json.loads(line))
    return auto


def evaluate(codes, gold, auto, out_prefix):
    G = {key(r): r for r in gold}
    A = {key(r): r for r in auto}
    gkeys, akeys = set(G), set(A)
    TP = gkeys & akeys
    FP = akeys - gkeys
    FN = gkeys - akeys
    tp, fp, fn = len(TP), len(FP), len(FN)
    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0

    print("=" * 64)
    print(f"Week 10 Stage 5D evaluation — {len(codes)} companies")
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
    for code in codes:
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

    with Path(out_prefix + "_details.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["status", "stock_code", "subscription_date",
                                          "event_context", "subscriber_name"])
        w.writeheader()
        w.writerows(details)

    summary = {
        "gold_pevc": len(G), "auto_pevc": len(A), "tp": tp, "fp": fp, "fn": fn,
        "precision": precision, "recall": recall, "f1": f1,
        "per_company": per_company,
    }
    Path(out_prefix + "_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print("===== FN (missed) =====")
    for k in sorted(FN):
        print(" ", k[0], k[1], k[2], k[3])
    print()
    print("===== FP (spurious) =====")
    for k in sorted(FP):
        print(" ", k[0], k[1], k[2], k[3])
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", required=True)
    ap.add_argument("--pred-dir", required=True)
    ap.add_argument("--codes", nargs="+", required=True)
    ap.add_argument("--out", required=True, help="output prefix (writes <out>_summary.json / _details.csv)")
    ap.add_argument("--exclude-prelisting", action="store_true",
                    help="exclude disclosure_form=prelisting rows from Recall denominator (阶段0边界规则)")
    args = ap.parse_args()
    gold = load_gold(args.gold, exclude_prelisting=args.exclude_prelisting)
    auto = load_auto(args.pred_dir, args.codes)
    evaluate(args.codes, gold, auto, args.out)


if __name__ == "__main__":
    main()
