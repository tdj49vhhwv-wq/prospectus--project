#!/usr/bin/env python3

import csv
import importlib.util
from pathlib import Path

ROOT = Path(".").resolve()

LONG = (
    ROOT
    / "week10/adaptive/long_syndicate_v1/"
      "long_syndicate_rows_v1.csv"
)

OUT = (
    ROOT
    / "week10/adaptive/audit/"
      "688795_institution_filter_audit.csv"
)

FROZEN = (
    ROOT
    / "week9/stage71_frozen/"
      "event_local_pevc.py"
)

spec = importlib.util.spec_from_file_location(
    "frozen_pevc",
    FROZEN
)

frozen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frozen)


with LONG.open(
    encoding="utf-8-sig"
) as f:
    rows = list(csv.DictReader(f))


text = frozen.load_text("688795")
aliases = frozen.alias_map(text)


def classify(name):
    clean = frozen.clean(name)

    accepted = frozen.is_institution(
        clean,
        aliases
    )

    return clean, accepted


audit = []

for i, r in enumerate(rows, 1):

    name, accepted = classify(
        r["investor"]
    )

    audit.append({
        "index": i,
        "investor_raw": r["investor"],
        "investor_clean": name,
        "frozen_is_institution": int(accepted),
        "status": (
            "ACCEPTED"
            if accepted
            else "REJECTED"
        ),
        "date": r["date"],
        "alias": r["alias"],
    })


with OUT.open(
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:

    fields = [
        "index",
        "investor_raw",
        "investor_clean",
        "frozen_is_institution",
        "status",
        "date",
        "alias",
    ]

    w = csv.DictWriter(
        f,
        fieldnames=fields
    )

    w.writeheader()
    w.writerows(audit)


accepted = [
    r for r in audit
    if r["status"] == "ACCEPTED"
]

rejected = [
    r for r in audit
    if r["status"] == "REJECTED"
]


print()
print("===== FILTER AUDIT SUMMARY =====")
print("Extracted :", len(audit))
print("Accepted  :", len(accepted))
print("Rejected  :", len(rejected))


print()
print("===== ACCEPTED BY FROZEN CLASSIFIER =====")

for r in accepted:
    print(
        f'{int(r["index"]):02d}',
        r["investor_clean"]
    )


print()
print("===== REJECTED BY FROZEN CLASSIFIER =====")

for r in rejected:
    print(
        f'{int(r["index"]):02d}',
        r["investor_clean"]
    )


print()
print("===== REJECTION NAME SIGNALS =====")

signals = {
    "投资": 0,
    "基金": 0,
    "资本": 0,
    "创投": 0,
    "创业": 0,
    "合伙": 0,
    "私募": 0,
    "资管": 0,
    "证券": 0,
    "保险": 0,
    "公司": 0,
}

for r in rejected:

    n = r["investor_clean"]

    for k in signals:
        if k in n:
            signals[k] += 1

for k, v in signals.items():
    print(f"{k:<6} {v}")


print()
print("Output:")
print(" ", OUT.relative_to(ROOT))
