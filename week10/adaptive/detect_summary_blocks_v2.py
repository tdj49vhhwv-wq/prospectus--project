#!/usr/bin/env python3

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ROUTES = ROOT / "week10/router/structural_routes_v1.csv"
UNIVERSE = ROOT / "week10/universe/prospectus_universe_v1_seed.csv"

OUT_DIR = ROOT / "week10/adaptive/summary_blocks_v2"
OUT_SUMMARY = ROOT / "week10/adaptive/summary_blocks_v2_summary.csv"

OUT_DIR.mkdir(parents=True, exist_ok=True)


SUMMARY_TERMS = [
    "股本变化",
    "股本变动",
    "股权变化",
    "股权变动",
    "股本演变",
    "历史沿革",
    "历次增资",
    "历次股本",
    "历次股权",
    "增资情况",
    "设立以来股本",
    "设立以来股权",
    "报告期内股本",
    "报告期内股权",
]

ACTION_TERMS = [
    "增资",
    "增加注册资本",
    "认购",
    "认缴",
    "新增股东",
    "股权转让",
    "股份转让",
    "整体变更",
    "注册资本",
]

COLUMN_TERMS = [
    "变更时间",
    "变更日期",
    "时间",
    "股东名称",
    "投资方",
    "增资方",
    "认购方",
    "增资金额",
    "认购金额",
    "注册资本",
    "变更后注册资本",
    "变更原因",
]

DATE_RE = re.compile(
    r"(?:19|20)\d{2}\s*年\s*\d{1,2}\s*月"
    r"(?:\s*\d{1,2}\s*日)?"
)

NUMBER_RE = re.compile(
    r"\d[\d,]*(?:\.\d+)?"
)


def read_csv(path):
    with path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


routes = {
    r["stock_code"]: r
    for r in read_csv(ROUTES)
}

universe = read_csv(UNIVERSE)


def load_text(row):
    parts = []

    for name in row["canonical_markdown_files"].split("|"):
        name = name.strip()

        if not name:
            continue

        p = ROOT / "week1/review" / name

        if p.exists():
            parts.append(
                p.read_text(
                    encoding="utf-8",
                    errors="ignore"
                )
            )

    return "\n\n".join(parts)


def clean_line(line):
    line = re.sub(r"<[^>]+>", " ", line)
    line = re.sub(r"\s+", " ", line)
    return line.strip()


def score_block(block):
    clean = "\n".join(
        clean_line(x)
        for x in block.splitlines()
        if clean_line(x)
    )

    summary_hits = [
        x for x in SUMMARY_TERMS
        if x in clean
    ]

    action_hits = [
        x for x in ACTION_TERMS
        if x in clean
    ]

    column_hits = [
        x for x in COLUMN_TERMS
        if x in clean
    ]

    dates = DATE_RE.findall(clean)
    numbers = NUMBER_RE.findall(clean)

    score = 0
    reasons = []

    if summary_hits:
        score += min(4, len(summary_hits) + 1)
        reasons.append(
            "summary=" + ",".join(summary_hits[:5])
        )

    if action_hits:
        score += min(4, len(action_hits))
        reasons.append(
            "actions=" + ",".join(action_hits[:5])
        )

    if column_hits:
        score += min(4, len(column_hits))
        reasons.append(
            "columns=" + ",".join(column_hits[:5])
        )

    if len(dates) >= 2:
        score += min(4, len(dates))
        reasons.append(f"dates={len(dates)}")

    if len(numbers) >= 10:
        score += 2
        reasons.append(f"numbers={len(numbers)}")

    # Summary/history blocks usually contain repeated transaction cues
    repeated_actions = sum(
        clean.count(x)
        for x in [
            "增资",
            "股权转让",
            "注册资本",
            "认购",
        ]
    )

    if repeated_actions >= 4:
        score += 3
        reasons.append(
            f"repeated_actions={repeated_actions}"
        )

    return score, reasons, clean


def candidate_windows(text):

    lines = text.splitlines()

    anchors = set()

    # Semantic heading / term anchors
    for i, line in enumerate(lines):
        if any(
            term in line
            for term in SUMMARY_TERMS
        ):
            anchors.add(i)

    # Column-header-like anchors
    for i, line in enumerate(lines):
        window = "\n".join(
            lines[i:min(len(lines), i + 10)]
        )

        hits = sum(
            1
            for term in COLUMN_TERMS
            if term in window
        )

        if hits >= 3:
            anchors.add(i)

    candidates = []

    for i in sorted(anchors):

        # Use a generous local window because flattened tables
        # often occupy many short lines.
        lo = max(0, i - 8)
        hi = min(len(lines), i + 80)

        raw = "\n".join(lines[lo:hi])

        score, reasons, clean = score_block(raw)

        if score < 7:
            continue

        candidates.append({
            "anchor_line": i + 1,
            "start_line": lo + 1,
            "end_line": hi,
            "score": score,
            "reasons": reasons,
            "text": clean[:15000],
        })

    # Deduplicate highly overlapping blocks
    deduped = []

    for c in sorted(
        candidates,
        key=lambda x: x["score"],
        reverse=True
    ):
        overlap = False

        for old in deduped:
            left = max(
                c["start_line"],
                old["start_line"]
            )
            right = min(
                c["end_line"],
                old["end_line"]
            )

            intersection = max(
                0,
                right - left
            )

            smaller = min(
                c["end_line"] - c["start_line"],
                old["end_line"] - old["start_line"]
            )

            if smaller and intersection / smaller > 0.6:
                overlap = True
                break

        if not overlap:
            deduped.append(c)

    return deduped[:20]


summary = []

print()
print("===== SUMMARY BLOCK DETECTION V2 =====")

for row in universe:

    code = row["stock_code"]
    route = routes.get(code)

    if not route:
        continue

    if (
        "summary_table_parser"
        not in route["activated_parsers"]
    ):
        continue

    text = load_text(row)
    candidates = candidate_windows(text)

    out = {
        "stock_code": code,
        "company": row["company_short_name"],
        "candidate_count": len(candidates),
        "candidates": candidates,
    }

    (
        OUT_DIR
        / f"{code}_{row['company_short_name']}.json"
    ).write_text(
        json.dumps(
            out,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    max_score = max(
        [x["score"] for x in candidates],
        default=0
    )

    summary.append({
        "stock_code": code,
        "company": row["company_short_name"],
        "candidate_count": len(candidates),
        "max_score": max_score,
    })

    print(
        code,
        row["company_short_name"],
        f"candidates={len(candidates)}",
        f"max_score={max_score}",
    )


with OUT_SUMMARY.open(
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=[
            "stock_code",
            "company",
            "candidate_count",
            "max_score",
        ]
    )

    writer.writeheader()
    writer.writerows(summary)


print()
print("===== TOP CANDIDATE PREVIEW =====")

for r in summary:

    p = (
        OUT_DIR
        / f"{r['stock_code']}_{r['company']}.json"
    )

    data = json.loads(
        p.read_text(encoding="utf-8")
    )

    print()
    print(
        r["stock_code"],
        r["company"]
    )

    if not data["candidates"]:
        print("  NO CANDIDATE")
        continue

    c = data["candidates"][0]

    print(
        "  score:",
        c["score"]
    )

    print(
        "  reasons:",
        " | ".join(c["reasons"])
    )

    preview = c["text"][:500].replace(
        "\n",
        " / "
    )

    print(
        "  preview:",
        preview
    )


print()
print("Output:")
print(
    " ",
    OUT_SUMMARY.relative_to(ROOT)
)
