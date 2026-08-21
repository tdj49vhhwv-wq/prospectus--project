#!/usr/bin/env python3

import csv
import json
from pathlib import Path
from collections import Counter

import numpy as np

ROOT = Path(__file__).resolve().parents[2]

INPUT = ROOT / "week10/taxonomy/semantic_taxonomy_v1.csv"

OUT = ROOT / "week10/router/structural_routes_v1.csv"

THRESHOLD_OUT = (
    ROOT
    / "week10/router"
    / "routing_thresholds_v1.json"
)


with INPUT.open(encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))


FEATURES = {
    "equity_complexity": "equity_signal",
    "investor_complexity": "investor_signal",
    "restructuring_complexity": "restructuring_signal",
    "summary_table_complexity": "summary_table_signal",
    "vie_complexity": "vie_signal",
    "date_complexity": "date_density",
    "long_list_complexity": "long_list_log",
}


def num(row, key):
    try:
        return float(row.get(key, 0) or 0)
    except Exception:
        return 0.0


# ============================================================
# Threshold calibration
#
# IMPORTANT:
# historical blind failures are excluded.
# ============================================================

calibration_rows = [
    r for r in rows
    if r["historical_role"]
    != "historical_blind_failure"
]

print()
print("===== THRESHOLD CALIBRATION =====")
print("All documents:", len(rows))
print("Calibration documents:", len(calibration_rows))
print(
    "Excluded historical blind failures:",
    len(rows) - len(calibration_rows),
)


thresholds = {}

for dimension, feature in FEATURES.items():

    vals = np.array([
        num(r, feature)
        for r in calibration_rows
    ])

    p75 = float(np.percentile(vals, 75))
    p90 = float(np.percentile(vals, 90))

    thresholds[dimension] = {
        "feature": feature,
        "p75": p75,
        "p90": p90,
    }

    print(
        f"{dimension:30s} "
        f"P75={p75:.6f} "
        f"P90={p90:.6f}"
    )


THRESHOLD_OUT.write_text(
    json.dumps(
        {
            "version": "routing_thresholds_v1",
            "calibration_rule":
                "exclude historical_blind_failure",
            "dimensions": thresholds,
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


# ============================================================
# Dimension classification
# ============================================================

def level(value, threshold):

    if value >= threshold["p90"]:
        return "EXTREME"

    if value >= threshold["p75"]:
        return "HIGH"

    return "NORMAL"


# ============================================================
# Parser routing rules
#
# Structural only.
# No company-name hardcodes.
# ============================================================

def routes_for(levels):

    routes = ["base_event_parser"]

    if (
        levels["summary_table_complexity"]
        in {"HIGH", "EXTREME"}
    ):
        routes.append("summary_table_parser")

    if (
        levels["investor_complexity"]
        in {"HIGH", "EXTREME"}
        or
        levels["long_list_complexity"]
        in {"HIGH", "EXTREME"}
    ):
        routes.append("long_syndicate_parser")

    if (
        levels["restructuring_complexity"]
        in {"HIGH", "EXTREME"}
    ):
        routes.append("restructuring_parser")

    if (
        levels["vie_complexity"]
        in {"HIGH", "EXTREME"}
    ):
        routes.append("vie_parser")

    if (
        levels["equity_complexity"]
        in {"HIGH", "EXTREME"}
    ):
        routes.append("dense_equity_history_parser")

    if (
        levels["date_complexity"]
        in {"HIGH", "EXTREME"}
    ):
        routes.append("date_anchor_enhancer")

    return routes


# ============================================================
# Apply frozen thresholds
# ============================================================

output = []

print()
print("===== STRUCTURAL ROUTES =====")

for row in rows:

    levels = {}

    for dimension, feature in FEATURES.items():

        value = num(row, feature)

        levels[dimension] = level(
            value,
            thresholds[dimension],
        )

    routes = routes_for(levels)

    out = {
        "document_id": row["document_id"],
        "stock_code": row["stock_code"],
        "company_short_name":
            row["company_short_name"],
        "board": row["board"],
        "historical_role":
            row["historical_role"],
    }

    for dimension in FEATURES:
        out[dimension] = levels[dimension]

    out["activated_parsers"] = " | ".join(routes)
    out["n_special_parsers"] = len(routes) - 1

    output.append(out)

    flags = [
        f"{k}={v}"
        for k, v in levels.items()
        if v != "NORMAL"
    ]

    print()
    print(
        row["stock_code"],
        row["company_short_name"],
    )

    print(
        "  flags:",
        " | ".join(flags)
        if flags
        else "NORMAL"
    )

    print(
        "  routes:",
        " | ".join(routes)
    )


fields = list(output[0].keys())

with OUT.open(
    "w",
    newline="",
    encoding="utf-8-sig",
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=fields,
    )

    writer.writeheader()
    writer.writerows(output)


# ============================================================
# Route frequency
# ============================================================

print()
print("===== ROUTE FREQUENCY =====")

counter = Counter()

for r in output:

    for route in r["activated_parsers"].split(" | "):
        counter[route] += 1


for route, count in counter.most_common():

    print(
        f"{route:32s} {count}"
    )


print()
print("Outputs:")
print(
    " ",
    THRESHOLD_OUT.relative_to(ROOT)
)
print(
    " ",
    OUT.relative_to(ROOT)
)
