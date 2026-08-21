#!/usr/bin/env python3

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ROUTES = ROOT / "week10/router/structural_routes_v1.csv"
UNIVERSE = ROOT / "week10/universe/prospectus_universe_v1_seed.csv"

OUT_DIR = ROOT / "week10/adaptive/summary_table_candidates"
OUT_SUMMARY = ROOT / "week10/adaptive/summary_table_candidate_summary.csv"

OUT_DIR.mkdir(parents=True, exist_ok=True)


KEYWORDS = [
    "股本变化",
    "股权变动",
    "历次增资",
    "历次股本",
    "历次股权",
    "增资情况",
    "股本演变",
    "历史沿革",
    "报告期内股本",
    "报告期内股权",
]

ACTION_TERMS = [
    "增资",
    "认购",
    "新增股东",
    "股权转让",
    "股份转让",
    "注册资本",
]

DATE_RE = re.compile(
    r"(?:19|20)\d{2}\s*年\s*\d{1,2}\s*月"
    r"(?:\s*\d{1,2}\s*日)?"
)

HTML_TABLE_RE = re.compile(
    r"<table\b.*?</table>",
    re.I | re.S
)


def load_csv(path):
    with path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


routes = {
    r["stock_code"]: r
    for r in load_csv(ROUTES)
}

universe = load_csv(UNIVERSE)


def load_text(row):
    names = [
        x.strip()
        for x in row["canonical_markdown_files"].split("|")
        if x.strip()
    ]

    parts = []

    for name in names:
        p = ROOT / "week1/review" / name
        if p.exists():
            parts.append(p.read_text(encoding="utf-8"))

    return "\n\n".join(parts)


def clean_html(s):
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def score_table(raw_table):
    plain = clean_html(raw_table)

    score = 0
    reasons = []

    kw_hits = [
        kw for kw in KEYWORDS
        if kw in plain
    ]

    if kw_hits:
        score += min(3, len(kw_hits))
        reasons.append(
            "keywords:" + ",".join(kw_hits[:5])
        )

    action_hits = [
        x for x in ACTION_TERMS
        if x in plain
    ]

    if action_hits:
        score += min(3, len(action_hits))
        reasons.append(
            "actions:" + ",".join(action_hits[:5])
        )

    dates = DATE_RE.findall(plain)

    if len(dates) >= 2:
        score += 2
        reasons.append(
            f"dates={len(dates)}"
        )

    row_count = len(
        re.findall(
            r"<tr\b",
            raw_table,
            flags=re.I
        )
    )

    if row_count >= 5:
        score += 1
        reasons.append(
            f"rows={row_count}"
        )

    if any(
        x in plain
        for x in [
            "变更后注册资本",
            "变更前注册资本",
            "增资金额",
            "新增注册资本",
            "股东名称",
            "认购金额",
            "认购数量",
        ]
    ):
        score += 2
        reasons.append(
            "structured_columns"
        )

    return score, reasons, plain, row_count


summary_rows = []


print()
print("===== SUMMARY TABLE DETECTION =====")


for row in universe:

    code = row["stock_code"]

    route = routes.get(code)

    if not route:
        continue

    if "summary_table_parser" not in route["activated_parsers"]:
        continue

    text = load_text(row)

    tables = list(
        HTML_TABLE_RE.finditer(text)
    )

    candidates = []

    for idx, m in enumerate(tables, 1):

        raw = m.group(0)

        score, reasons, plain, row_count = (
            score_table(raw)
        )

        if score < 4:
            continue

        candidates.append({
            "table_index": idx,
            "score": score,
            "reasons": reasons,
            "row_count": row_count,
            "plain_text": plain[:8000],
            "raw_html": raw[:20000],
        })


    # Markdown-like tables / structured text fallback
    lines = text.splitlines()

    for i, line in enumerate(lines):

        if line.count("|") < 2:
            continue

        window = "\n".join(
            lines[max(0, i-2):min(len(lines), i+12)]
        )

        if not any(
            kw in window
            for kw in KEYWORDS + ACTION_TERMS
        ):
            continue

        date_hits = DATE_RE.findall(window)

        pipe_rows = sum(
            1
            for x in window.splitlines()
            if x.count("|") >= 2
        )

        if pipe_rows < 3:
            continue

        score = (
            2
            + min(2, len(date_hits))
            + min(2, pipe_rows // 3)
        )

        candidates.append({
            "table_index": f"md_{i}",
            "score": score,
            "reasons": [
                f"markdown_table_rows={pipe_rows}",
                f"dates={len(date_hits)}",
            ],
            "row_count": pipe_rows,
            "plain_text": window[:8000],
            "raw_html": "",
        })


    out_json = (
        OUT_DIR
        / f"{code}_{row['company_short_name']}.json"
    )

    out_json.write_text(
        json.dumps(
            {
                "stock_code": code,
                "company":
                    row["company_short_name"],
                "candidate_count":
                    len(candidates),
                "candidates":
                    candidates,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    max_score = (
        max(
            [c["score"] for c in candidates],
            default=0
        )
    )

    summary_rows.append({
        "stock_code": code,
        "company":
            row["company_short_name"],
        "candidate_count":
            len(candidates),
        "max_score":
            max_score,
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
    encoding="utf-8-sig",
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=[
            "stock_code",
            "company",
            "candidate_count",
            "max_score",
        ],
    )

    writer.writeheader()
    writer.writerows(summary_rows)


print()
print("Output:")
print(
    " ",
    OUT_SUMMARY.relative_to(ROOT)
)
