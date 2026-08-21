#!/usr/bin/env python3

import csv
import re
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Adaptive v1 already contains:
# frozen baseline + 沐曦 summary-table additions.
V1 = (
    ROOT
    / "week10"
    / "adaptive"
    / "final_v1"
    / "adaptive_blind_pevc_rows.csv"
)

LONG = (
    ROOT
    / "week10"
    / "adaptive"
    / "long_syndicate_v1"
    / "long_syndicate_rows_v1.csv"
)

OUT = (
    ROOT
    / "week10"
    / "adaptive"
    / "final_v2"
    / "adaptive_blind_pevc_rows_v2.csv"
)

ADDITIONS = (
    ROOT
    / "week10"
    / "adaptive"
    / "final_v2"
    / "long_syndicate_additions_v2.csv"
)


# ============================================================
# Reuse frozen Stage 7.1 institutional classification.
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


def read_csv(path):
    with path.open(
        encoding="utf-8-sig"
    ) as f:
        return list(csv.DictReader(f))


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


v1 = read_csv(V1)
long_rows = read_csv(LONG)


# ============================================================
# Convert Stage 4E long-syndicate rows into blind schema.
# ============================================================

converted = []

# Alias map is derived from prospectus using frozen logic.
text = frozen.load_text("688795")
aliases = frozen.alias_map(text)

for r in long_rows:

    if r["code"] != "688795":
        continue

    name = frozen.clean(r["investor"])

    if not name:
        continue

    # Use exactly the same institution decision logic
    # as frozen Stage 7.1.
    if not frozen.is_institution(
        name,
        aliases
    ):
        continue

    if any(
        bad in name
        for bad in (
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

    converted.append({
        "stock_code": "688795",
        "subscription_date": r["date"][:7],
        "event_context": "增资",
        "subscriber_name": name,

        # IMPORTANT:
        # 522452.9091 / 7002.8217 are syndicate totals.
        # Do NOT assign totals to every investor.
        "amount_subscribed": "",
        "shares_subscribed": "",
        "price_per_share": "",

        "source":
            "week10_long_syndicate_alias_v1",

        "evidence_text":
            r.get("evidence", "")[:1000],
    })


# ============================================================
# Merge: Adaptive v1 wins on duplicates.
# ============================================================

merged = {
    key(r): r
    for r in v1
}

new_unique = []

for r in converted:

    k = key(r)

    if k in merged:
        continue

    merged[k] = r
    new_unique.append(r)


final_rows = list(merged.values())

final_rows.sort(
    key=lambda r: (
        r["stock_code"],
        r["subscription_date"],
        r["event_context"],
        norm(r["subscriber_name"]),
    )
)


FIELDS = [
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
    encoding="utf-8-sig",
) as f:

    w = csv.DictWriter(
        f,
        fieldnames=FIELDS,
    )

    w.writeheader()
    w.writerows(final_rows)


with ADDITIONS.open(
    "w",
    newline="",
    encoding="utf-8-sig",
) as f:

    w = csv.DictWriter(
        f,
        fieldnames=FIELDS,
    )

    w.writeheader()
    w.writerows(new_unique)


print()
print("===== ADAPTIVE V2 MERGE =====")

print(
    "Adaptive v1 rows:",
    len(v1)
)

print(
    "Raw long-syndicate rows:",
    len(long_rows)
)

print(
    "Institutional long-syndicate rows:",
    len(converted)
)

print(
    "New unique rows added:",
    len(new_unique)
)

print(
    "Adaptive v2 final rows:",
    len(final_rows)
)


print()
print("By company:")

for code in ["688795", "688802"]:

    v1_n = sum(
        r["stock_code"] == code
        for r in v1
    )

    v2_n = sum(
        r["stock_code"] == code
        for r in final_rows
    )

    print(
        code,
        f"v1={v1_n}",
        f"v2={v2_n}",
        f"delta={v2_n-v1_n}",
    )


print()
print("Output:")
print(" ", OUT.relative_to(ROOT))
print(" ", ADDITIONS.relative_to(ROOT))
