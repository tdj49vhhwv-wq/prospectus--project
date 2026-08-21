#!/usr/bin/env python3

import csv
import json
import re
import sys
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

BASELINE = (
    ROOT
    / "week9"
    / "blind_run1"
    / "week9_blind_run1_pevc_rows.csv"
)

ADAPTIVE_DIR = (
    ROOT
    / "week10"
    / "adaptive"
    / "investor_rows_v2"
)

OUT = (
    ROOT
    / "week10"
    / "adaptive"
    / "final_v1"
    / "adaptive_blind_pevc_rows.csv"
)

ADDITIONS = (
    ROOT
    / "week10"
    / "adaptive"
    / "final_v1"
    / "adaptive_additions_only.csv"
)


# ============================================================
# Reuse Stage 7.1 frozen institution logic
# ============================================================

FROZEN = (
    ROOT
    / "week9"
    / "stage71_frozen"
    / "event_local_pevc.py"
)

spec = importlib.util.spec_from_file_location(
    "frozen_pevc",
    FROZEN
)

frozen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frozen)


def norm(x):
    s = str(x or "").strip().upper()
    s = s.replace("（", "(").replace("）", ")")
    s = re.sub(r"\s+", "", s)
    return s.strip("，。；、,;:")


def load_baseline():
    with BASELINE.open(
        encoding="utf-8-sig"
    ) as f:
        return list(csv.DictReader(f))


def event_context(event_type):
    if event_type == "增资":
        return "增资"

    if event_type == "增资及股权转让":
        return "增资及股权转让"

    if event_type == "股权转让":
        return "股权转让"

    return event_type


def adaptive_rows():
    rows = []

    for path in sorted(
        ADAPTIVE_DIR.glob("*.jsonl")
    ):
        events = [
            json.loads(x)
            for x in path.read_text(
                encoding="utf-8"
            ).splitlines()
            if x.strip()
        ]

        if not events:
            continue

        code = events[0]["stock_code"]

        # Stage 4D Blind evaluation only evaluates
        # historical blind companies.
        if code not in {
            "688795",
            "688802",
        }:
            continue

        # Obtain alias map from the prospectus text
        # using the frozen parser logic.
        text = frozen.load_text(code)
        aliases = frozen.alias_map(text)

        for e in events:

            # v1 adaptive module is currently intended
            # for financing / subscription events.
            if e.get("event_type") not in {
                "增资",
                "增资及股权转让",
            }:
                continue

            date = str(
                e.get("event_date", "")
            )[:7]

            if not date:
                continue

            investors = (
                e.get(
                    "investors_normalized_v2",
                    []
                )
            )

            for name in investors:

                name = frozen.clean(name)

                if not name:
                    continue

                if not frozen.is_institution(
                    name,
                    aliases
                ):
                    continue

                # Same de-noising principle as frozen parser.
                if any(
                    k in name
                    for k in (
                        "注册资本",
                        "新增股份",
                        "股东大会",
                        "发行人",
                        "本次",
                        "增资协议",
                        "认购价格",
                        "万元",
                    )
                ):
                    continue

                rows.append({
                    "stock_code":
                        code,

                    "subscription_date":
                        date,

                    "event_context":
                        event_context(
                            e["event_type"]
                        ),

                    "subscriber_name":
                        name,

                    # Group-level amount must NOT be assigned
                    # to every investor.
                    "amount_subscribed":
                        "",

                    "shares_subscribed":
                        "",

                    "price_per_share":
                        "",

                    "source":
                        "week10_adaptive_v1",

                    "evidence_text":
                        e.get(
                            "evidence_text",
                            ""
                        )[:1000],
                })

    return rows


baseline = load_baseline()
adds = adaptive_rows()


# ============================================================
# Deterministic merge
# ============================================================

def row_key(r):
    return (
        str(
            r.get("stock_code", "")
        ).strip(),

        str(
            r.get("subscription_date", "")
        )[:7],

        str(
            r.get("event_context", "")
        ).strip(),

        norm(
            r.get("subscriber_name", "")
        ),
    )


merged = {}

# Frozen baseline wins on duplicates.
for r in baseline:
    merged[row_key(r)] = r

new_count = 0

for r in adds:
    k = row_key(r)

    if k not in merged:
        merged[k] = r
        new_count += 1


final_rows = list(
    merged.values()
)

final_rows.sort(
    key=lambda r: (
        r["stock_code"],
        r["subscription_date"],
        r["event_context"],
        norm(r["subscriber_name"]),
    )
)


fields = [
    "stock_code",
    "subscription_date",
    "event_context",
    "subscriber_name",
    "amount_subscribed",
    "shares_subscribed",
    "price_per_share",
    "source",
    "evidence_text",
]


with OUT.open(
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:
    w = csv.DictWriter(
        f,
        fieldnames=fields
    )
    w.writeheader()
    w.writerows(final_rows)


with ADDITIONS.open(
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:
    w = csv.DictWriter(
        f,
        fieldnames=fields
    )
    w.writeheader()
    w.writerows(adds)


print("===== ADAPTIVE MERGE =====")
print("Frozen rows:", len(baseline))
print("Adaptive candidate rows:", len(adds))
print("New unique rows added:", new_count)
print("Final merged rows:", len(final_rows))

print()
print("By company:")

for code in ["688795", "688802"]:
    base_n = sum(
        r["stock_code"] == code
        for r in baseline
    )

    add_n = sum(
        r["stock_code"] == code
        for r in adds
    )

    final_n = sum(
        r["stock_code"] == code
        for r in final_rows
    )

    print(
        code,
        f"baseline={base_n}",
        f"adaptive_candidates={add_n}",
        f"final={final_n}",
    )

print()
print("Output:", OUT.relative_to(ROOT))
