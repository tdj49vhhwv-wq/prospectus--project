#!/usr/bin/env python3

import csv
import random
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[2]

POOL = ROOT / "week10/universe/candidate_pool_v1.csv"
QUOTA = ROOT / "week10/universe/expansion_quota_v1.csv"
OUT = ROOT / "week10/universe/selected_expansion_v1.csv"

RANDOM_SEED = 202610


def load_csv(path):
    with path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


pool = load_csv(POOL)
quota = load_csv(QUOTA)

eligible = [
    r for r in pool
    if r.get("eligible", "").strip().lower() in {"yes", "1", "true"}
]

groups = defaultdict(list)

for r in eligible:
    key = (r["board"], r["ipo_year"])
    groups[key].append(r)

rng = random.Random(RANDOM_SEED)

selected = []

for q in quota:
    board = q["board"]
    year = q["year"]
    n = int(q["target_new"])

    candidates = sorted(
        groups.get((board, year), []),
        key=lambda r: r["stock_code"]
    )

    if len(candidates) < n:
        print(
            f"BLOCKED {board} {year}: "
            f"need={n}, eligible={len(candidates)}"
        )
        continue

    picks = rng.sample(candidates, n)

    for r in picks:
        x = dict(r)
        x["sampling_seed"] = RANDOM_SEED
        x["stratum"] = f"{board}_{year}"
        selected.append(x)

fields = [
    "stock_code",
    "company_short_name",
    "exchange",
    "board",
    "listing_date",
    "ipo_year",
    "official_source_url",
    "eligible",
    "exclusion_reason",
    "sampling_seed",
    "stratum",
]

with OUT.open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(selected)

print()
print("Selected:", len(selected))
print("Seed:", RANDOM_SEED)
print("Output:", OUT.relative_to(ROOT))
