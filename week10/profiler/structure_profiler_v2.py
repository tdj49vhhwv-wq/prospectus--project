#!/usr/bin/env python3
"""Stage 5C — Structure Profiler v2 (DEV 12, independent cross-board sample).

Profiles the 12 DEV prospectuses converted to canonical Markdown by MinerU,
computes the SAME 7 semantic routing signals used by the frozen v1 taxonomy,
and applies the frozen routing thresholds (`routing_thresholds_v1.json`) to
test whether the structural router generalizes to a board distribution the
original 25-company seed did not cover (Main / ChiNext / BSE, zero STAR).

Term lists and regexes are verbatim from `profile_prospectus.py` (v1) so the
DEV features are directly comparable to the original 25.

Outputs:
  week10/profiler/structure_features_v2.csv    — raw features (DEV 12)
  week10/router/semantic_signals_v2.csv        — 7 signals (DEV 12)
  week10/router/router_application_v2.csv      — frozen thresholds applied
"""

from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]

CANONICAL_DIR = ROOT / "week10/canonical"
MANIFEST = ROOT / "week10/acquisition/manifests/acquisition_manifest_v1.csv"
ORIG_SIGNALS = ROOT / "week10/taxonomy/semantic_taxonomy_v1.csv"
THRESHOLDS = ROOT / "week10/router/routing_thresholds_v1.json"

OUT_FEATURES = ROOT / "week10/profiler/structure_features_v2.csv"
OUT_SIGNALS = ROOT / "week10/router/semantic_signals_v2.csv"
OUT_ROUTES = ROOT / "week10/router/router_application_v2.csv"

# --- verbatim term lists from profile_prospectus.py (v1) -----------------
EQUITY_TERMS = [
    "历史沿革", "股本演变", "股本形成", "股权演变", "历次增资",
    "增资", "股权转让", "整体变更", "设立", "股份制改造", "发行融资",
]
RESTRUCTURING_TERMS = [
    "重大资产重组", "重组", "吸收合并", "资产置换", "业务重组", "同一控制下",
]
INVESTOR_TERMS = [
    "投资", "基金", "创投", "资本", "合伙企业", "认购", "认缴",
    "增资方", "新增股东",
]
VIE_TERMS = [
    "VIE", "协议控制", "可变利益实体", "境外架构", "红筹", "返程投资", "WFOE",
]
SUMMARY_TABLE_TERMS = [
    "报告期内股本变化", "报告期内股权变动", "历次股本变化",
    "历次股权变动", "股本变化情况", "股权变动情况",
]

ROUTER_DIMENSIONS = {
    "equity_complexity": "equity_signal",
    "investor_complexity": "investor_signal",
    "restructuring_complexity": "restructuring_signal",
    "summary_table_complexity": "summary_table_signal",
    "vie_complexity": "vie_signal",
    "date_complexity": "date_density",
    "long_list_complexity": "long_list_log",
}


def count_terms(text, terms):
    return {term: text.lower().count(term.lower()) for term in terms}


def date_count(text):
    patterns = [
        r"(?:19|20)\d{2}\s*年\s*\d{1,2}\s*月(?:\s*\d{1,2}\s*日)?",
        r"(?:19|20)\d{2}[-/.]\d{1,2}(?:[-/.]\d{1,2})?",
    ]
    return sum(len(re.findall(p, text)) for p in patterns)


def markdown_headings(lines):
    return [
        line.strip()
        for line in lines
        if re.match(r"^\s{0,3}#{1,6}\s+\S", line)
    ]


def longest_delimited_line(lines):
    best = 0
    for line in lines:
        s = line.strip()
        if len(s) > 1500:
            continue
        n = len(re.findall(r"[、，,；;]", s))
        if n > best:
            best = n
    return best


def compute_features(stem: str, text: str, meta: dict) -> dict:
    lines = text.splitlines()
    headings = markdown_headings(lines)
    char_count = len(text)
    nonempty = [x for x in lines if x.strip()]

    equity = count_terms(text, EQUITY_TERMS)
    restruct = count_terms(text, RESTRUCTURING_TERMS)
    investor = count_terms(text, INVESTOR_TERMS)
    vie = count_terms(text, VIE_TERMS)
    summary = count_terms(text, SUMMARY_TABLE_TERMS)

    equity_total = sum(equity.values())
    restruct_total = sum(restruct.values())
    investor_total = sum(investor.values())
    vie_total = sum(vie.values())
    summary_total = sum(summary.values())

    md_table_rows = [
        s for s in nonempty
        if s.strip().count("|") >= 2 and len(s.strip()) >= 5
    ]
    narrative = [
        x for x in nonempty
        if "|" not in x and not x.lstrip().startswith("<")
    ]

    return {
        "document_id": meta.get("sample_id", stem),
        "stock_code": meta["stock_code"],
        "company_short_name": meta["company_name"],
        "board": meta["board"],
        "historical_role": meta["role"],
        "canonical_parts": 1,
        "missing_parts": 0,
        "character_count": char_count,
        "line_count": len(lines),
        "nonempty_line_count": len(nonempty),
        "markdown_heading_count": len(headings),
        "numbered_heading_count": sum(
            1 for line in lines
            if re.search(
                r"^\s*[一二三四五六七八九十]+[、.]"
                r"|^\s*[（(]\d+[）)]"
                r"|^\s*\d+[、.]"
                r"|^\s*\d+\.\d+",
                line,
            )
        ),
        "equity_heading_count": sum(
            1 for h in headings if any(t in h for t in EQUITY_TERMS)
        ),
        "html_table_count": len(re.findall(r"<table\b", text, re.I)),
        "markdown_table_line_count": len(md_table_rows),
        "mermaid_count": len(re.findall(r"```mermaid", text, re.I)),
        "image_count": len(re.findall(r"!\[[^\]]*\]\([^)]+\)", text)),
        "page_marker_count": len(re.findall(r"##\s*第\s*\d+\s*页", text)),
        "date_expression_count": date_count(text),
        "equity_term_total": equity_total,
        "restructuring_term_total": restruct_total,
        "investor_term_total": investor_total,
        "vie_term_total": vie_total,
        "summary_table_term_total": summary_total,
        "longest_delimited_line_score": longest_delimited_line(lines),
        "table_line_ratio": round(
            len(md_table_rows) / max(1, len(nonempty)), 6
        ),
        "heading_density_per_10k_chars": round(
            len(headings) / max(1, char_count) * 10000, 6
        ),
        "equity_signal_per_10k_chars": round(
            equity_total / max(1, char_count) * 10000, 6
        ),
        "investor_signal_per_10k_chars": round(
            investor_total / max(1, char_count) * 10000, 6
        ),
        "narrative_line_ratio": round(
            len(narrative) / max(1, len(nonempty)), 6
        ),
    }


def semantic_signals(f: dict) -> dict:
    chars = max(f["character_count"], 1)
    return {
        "equity_signal": f["equity_signal_per_10k_chars"],
        "investor_signal": f["investor_signal_per_10k_chars"],
        "restructuring_signal": f["restructuring_term_total"] / chars * 10000,
        "summary_table_signal": f["summary_table_term_total"] / chars * 10000,
        "vie_signal": f["vie_term_total"] / chars * 10000,
        "date_density": f["date_expression_count"] / chars * 10000,
        "long_list_log": math.log1p(f["longest_delimited_line_score"]),
    }


def load_manifest() -> dict:
    with MANIFEST.open(newline="", encoding="utf-8") as fh:
        rows = [dict(r) for r in csv.DictReader(fh)]
    clean_rows = [{k.lstrip("﻿"): v for k, v in r.items()} for r in rows]
    return {r["stock_code"]: r for r in clean_rows if r.get("role") == "DEV"}


def load_orig_signals() -> list[dict]:
    with ORIG_SIGNALS.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def level(value, threshold):
    if value >= threshold["p90"]:
        return "EXTREME"
    if value >= threshold["p75"]:
        return "HIGH"
    return "NORMAL"


def routes_for(levels):
    routes = ["base_event_parser"]
    if levels["summary_table_complexity"] in {"HIGH", "EXTREME"}:
        routes.append("summary_table_parser")
    if (levels["investor_complexity"] in {"HIGH", "EXTREME"}
            or levels["long_list_complexity"] in {"HIGH", "EXTREME"}):
        routes.append("long_syndicate_parser")
    if levels["restructuring_complexity"] in {"HIGH", "EXTREME"}:
        routes.append("restructuring_parser")
    if levels["vie_complexity"] in {"HIGH", "EXTREME"}:
        routes.append("vie_parser")
    if levels["equity_complexity"] in {"HIGH", "EXTREME"}:
        routes.append("dense_equity_history_parser")
    if levels["date_complexity"] in {"HIGH", "EXTREME"}:
        routes.append("date_anchor_enhancer")
    return routes


def main() -> None:
    meta_by_code = load_manifest()
    dev_codes = sorted(meta_by_code)

    # --- compute features -------------------------------------------------
    features = []
    missing = []
    for code in dev_codes:
        stem_prefix = f"{code}_"
        mds = sorted(CANONICAL_DIR.glob(f"{stem_prefix}*.md"))
        if not mds:
            missing.append(code)
            continue
        text = mds[0].read_text(encoding="utf-8")
        features.append(compute_features(mds[0].stem, text, meta_by_code[code]))

    print(f"\nDEV canonical files found: {len(features)}/{len(dev_codes)}")
    if missing:
        print("MISSING canonical markdown for:", missing)

    # --- write raw features ----------------------------------------------
    fields = list(features[0].keys())
    with OUT_FEATURES.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(features)

    # --- 7 semantic signals ----------------------------------------------
    sig_rows = []
    for f in features:
        s = semantic_signals(f)
        s.update({
            "document_id": f["document_id"],
            "stock_code": f["stock_code"],
            "company_short_name": f["company_short_name"],
            "board": f["board"],
            "historical_role": f["historical_role"],
        })
        sig_rows.append(s)

    with OUT_SIGNALS.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(sig_rows[0].keys()))
        w.writeheader()
        w.writerows(sig_rows)

    # --- load original 25 + frozen thresholds ----------------------------
    orig = load_orig_signals()
    thresholds = json.loads(THRESHOLDS.read_text(encoding="utf-8"))

    signal_names = list(ROUTER_DIMENSIONS.values())

    # per-signal original distribution for comparison
    print("\n===== DEV vs ORIGINAL-25 SIGNAL DISTRIBUTION =====")
    print(f"{'signal':24s} {'orig_min':>10s} {'orig_med':>10s} "
          f"{'orig_max':>10s} {'#DEV<min':>9s} {'#DEV>max':>9s}")
    for name in signal_names:
        orig_vals = np.array([float(r[name]) for r in orig])
        dev_vals = np.array([s[name] for s in sig_rows])
        n_below = int(np.sum(dev_vals < orig_vals.min()))
        n_above = int(np.sum(dev_vals > orig_vals.max()))
        print(f"{name:24s} {orig_vals.min():10.4f} "
              f"{np.median(orig_vals):10.4f} {orig_vals.max():10.4f} "
              f"{n_below:9d} {n_above:9d}")

    # --- apply frozen thresholds -> routes --------------------------------
    print("\n===== ROUTER APPLICATION (frozen v1 thresholds) =====")
    route_rows = []
    for s in sig_rows:
        levels = {}
        for dim, feature in ROUTER_DIMENSIONS.items():
            levels[dim] = level(s[feature], thresholds["dimensions"][dim])
        routes = routes_for(levels)

        out = {
            "document_id": s["document_id"],
            "stock_code": s["stock_code"],
            "company_short_name": s["company_short_name"],
            "board": s["board"],
            "historical_role": s["historical_role"],
        }
        for dim in ROUTER_DIMENSIONS:
            out[dim] = levels[dim]
        out["activated_parsers"] = " | ".join(routes)
        out["n_special_parsers"] = len(routes) - 1
        route_rows.append(out)

        flags = [f"{k}={v}" for k, v in levels.items() if v != "NORMAL"]
        print(f"{s['stock_code']:>8} {s['company_short_name']:<8} "
              f"[{s['board']}]  "
              f"{' | '.join(flags) if flags else 'NORMAL'}")
        print(f"          routes: {' | '.join(routes)}")

    with OUT_ROUTES.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(route_rows[0].keys()))
        w.writeheader()
        w.writerows(route_rows)

    # --- board-level summary ---------------------------------------------
    print("\n===== BOARD-LEVEL ROUTE SUMMARY (DEV 12) =====")
    from collections import Counter
    for board in ["Main", "ChiNext", "BSE"]:
        sub = [r for r in route_rows if r["board"] == board]
        n_special = [r["n_special_parsers"] for r in sub]
        flag_count = Counter()
        for r in sub:
            for k, v in r.items():
                if k in ROUTER_DIMENSIONS and v != "NORMAL":
                    flag_count[k] += 1
        print(f"{board:10s} n={len(sub)} "
              f"special_parsers mean={np.mean(n_special):.2f} "
              f"flags={dict(flag_count)}")

    print("\nOutputs:")
    print(" ", OUT_FEATURES.relative_to(ROOT))
    print(" ", OUT_SIGNALS.relative_to(ROOT))
    print(" ", OUT_ROUTES.relative_to(ROOT))


if __name__ == "__main__":
    main()
