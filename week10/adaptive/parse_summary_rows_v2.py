#!/usr/bin/env python3

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

UNIVERSE = ROOT / "week10/universe/prospectus_universe_v1_seed.csv"
ROUTES = ROOT / "week10/router/structural_routes_v1.csv"

OUT_DIR = ROOT / "week10/adaptive/summary_rows_v2"
OUT_SUMMARY = ROOT / "week10/adaptive/summary_rows_v2_summary.csv"

OUT_DIR.mkdir(parents=True, exist_ok=True)


DATE_RE = re.compile(
    r"((?:19|20)\d{2})\s*年\s*"
    r"(\d{1,2})\s*月"
    r"(?:\s*(\d{1,2})\s*日)?"
)

ROW_NUMBER_RE = re.compile(
    r"^\s*(\d{1,2})\s*$"
)

PAGE_RE = re.compile(
    r"^\s*##\s*第\d+页\s*$"
)

PAGE_CODE_RE = re.compile(
    r"^\s*1-1-\d+\s*$"
)


def read_csv(path):
    with path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


universe = read_csv(UNIVERSE)
routes = {
    r["stock_code"]: r
    for r in read_csv(ROUTES)
}


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

    return "\n".join(parts)


def clean_lines(text):
    raw = text.splitlines()
    out = []

    for line in raw:
        s = line.strip()

        if not s:
            continue

        if PAGE_RE.match(s):
            continue

        if PAGE_CODE_RE.match(s):
            continue

        if "招股说明书" in s and len(s) < 80:
            continue

        # repeated flattened table headers
        if s in {
            "序号",
            "时间",
            "股权变动",
            "股权变动情况",
        }:
            continue

        out.append(s)

    return out


def find_summary_region(lines):
    """
    Locate the equity-change summary region.
    """

    start = None

    for i, line in enumerate(lines):
        if (
            "经历七次增资" in line
            or "股本和股东变化情况" in line
            or "股本、股东变化情况" in line
            or "历次股本及股东变化" in line
        ):
            start = i
            break

    if start is None:
        return lines

    # stop when next clearly unrelated subsection begins
    stop_terms = [
        "出资瑕疵",
        "工会及职工持股会",
        "关于对赌协议",
        "代持及解除",
    ]

    end = len(lines)

    for j in range(start + 1, len(lines)):
        if any(x in lines[j] for x in stop_terms):
            end = j
            break

    return lines[start:end]


def merge_row_lines(lines):
    """
    Parse flattened row pattern:

    10
    2025 年3 月
    报告期第七
    次增资
    1、...
    2、...

    into one row.
    """

    row_starts = []

    for i, line in enumerate(lines):
        m = ROW_NUMBER_RE.match(line)

        if not m:
            continue

        # Require a date shortly after row number.
        lookahead = " ".join(
            lines[i + 1:min(len(lines), i + 6)]
        )

        if DATE_RE.search(lookahead):
            row_starts.append(i)

    if not row_starts:
        return []

    rows = []

    for idx, start in enumerate(row_starts):
        end = (
            row_starts[idx + 1]
            if idx + 1 < len(row_starts)
            else len(lines)
        )

        chunk = lines[start:end]

        if len(chunk) < 2:
            continue

        row_no = int(chunk[0])

        text = " ".join(chunk[1:])
        text = re.sub(r"\s+", " ", text).strip()

        dm = DATE_RE.search(text)

        if not dm:
            continue

        y, mo, d = dm.groups()

        event_date = (
            f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
            if d
            else f"{int(y):04d}-{int(mo):02d}"
        )

        # Remove the leading date from remainder.
        after_date = text[dm.end():].strip()

        rows.append({
            "row_no": row_no,
            "event_date": event_date,
            "raw_text": after_date,
        })

    return rows


def classify_row(text):
    compact = re.sub(r"\s+", "", text)

    if "资本公积转增" in compact:
        return "资本公积转增"

    if (
        "增资" in compact
        and (
            "股权转让" in compact
            or "股份转让" in compact
        )
    ):
        # Only call mixed when the label itself is mixed.
        # Do NOT use body spillover.
        prefix = compact[:80]

        if (
            "增资" in prefix
            and (
                "股权转让" in prefix
                or "股份转让" in prefix
            )
        ):
            return "增资及股权转让"

    if "增资" in compact:
        return "增资"

    if "股权转让" in compact or "股份转让" in compact:
        return "股权转让"

    if "整体变更" in compact:
        return "整体变更"

    return "其他"


def extract_event_label(text, event_type):
    """
    Keep the semantic row label separate from body.
    """

    patterns = [
        r"(报告期第.{0,25}?次增资)",
        r"(报告期第.{0,35}?次(?:及第.{0,15}?次)?股权转让)",
        r"(资本公积转增)",
        r"(第.{0,20}?次增资)",
        r"(第.{0,30}?次股权转让)",
    ]

    for p in patterns:
        m = re.search(p, text)

        if m:
            return m.group(1)

    return event_type


def extract_amount(text):
    patterns = [
        r"合计\s*([\d,]+(?:\.\d+)?)\s*万元人民币的投资金额",
        r"合计\s*([\d,]+(?:\.\d+)?)\s*万元",
        r"投资金额[^。\d]{0,20}([\d,]+(?:\.\d+)?)\s*万元",
    ]

    for p in patterns:
        m = re.search(p, text)

        if m:
            return float(m.group(1).replace(",", ""))

    return None


def extract_shares(text):
    patterns = [
        r"认购公司(?:本次)?发行新股\s*([\d,]+(?:\.\d+)?)\s*股",
        r"认购公司本次发行新股\s*([\d,]+(?:\.\d+)?)\s*股",
    ]

    for p in patterns:
        m = re.search(p, text)

        if m:
            return float(m.group(1).replace(",", ""))

    return None


def extract_capital_after(text):
    patterns = [
        r"注册资本(?:为|增加至|增至)\s*"
        r"([\d,]+(?:\.\d+)?)\s*(万元|元)",
        r"注册资本由[\d,.]+\s*(?:万元|元)"
        r"增加至\s*([\d,]+(?:\.\d+)?)\s*(万元|元)",
    ]

    for p in patterns:
        m = re.search(p, text)

        if m:
            return {
                "value": float(
                    m.group(1).replace(",", "")
                ),
                "unit": m.group(2),
            }

    return None


def extract_investor_groups(text):
    """
    Extract all investor groups in one row.

    A row may contain multiple pricing groups, e.g. 2023-12.
    """

    groups = []

    patterns = [
        re.compile(
            r"(?:\d+[、.]\s*)?"
            r"([^。；]{1,2500}?)"
            r"按照每\s*1\s*元注册资本"
            r"[\d,.]+\s*元的价格"
            r"[^。；]{0,150}?"
            r"(?:认购|出资认购)"
        ),

        re.compile(
            r"(?:\d+[、.]\s*)?"
            r"([^。；]{1,2500}?)"
            r"各以人民币[\d,.]+\s*元"
            r"[/／]每一元注册资本"
            r"[^。；]{0,150}?"
            r"(?:认购|出资认购)"
        ),

        re.compile(
            r"(?:\d+[、.]\s*)?"
            r"([^。；]{1,3000}?)"
            r"以合计[\d,]+(?:\.\d+)?\s*万元人民币的投资金额"
            r"[^。；]{0,120}?"
            r"认购"
        ),
    ]

    for pat in patterns:
        for m in pat.finditer(text):
            raw = m.group(1)

            # Remove row label residue.
            raw = re.sub(
                r"^.*?(?:次增资)\s*",
                "",
                raw,
                count=1
            )

            raw = re.sub(
                r"^\d+[、.]\s*",
                "",
                raw
            )

            raw = raw.strip(" ，、；;:")

            if raw and raw not in groups:
                groups.append(raw)

    return groups


def count_hint(groups):
    count = 0

    for raw in groups:
        pieces = [
            x.strip()
            for x in re.split(
                r"[、，,；;]",
                raw
            )
            if x.strip()
        ]

        count += len(pieces)

    return count


print()
print("===== ROW-AWARE SUMMARY PARSING =====")

summary = []


for row in universe:
    code = row["stock_code"]

    route = routes.get(code)

    if not route:
        continue

    if "summary_table_parser" not in route["activated_parsers"]:
        continue

    text = load_text(row)

    lines = clean_lines(text)
    region = find_summary_region(lines)

    parsed_rows = merge_row_lines(region)

    events = []

    for r in parsed_rows:
        event_type = classify_row(r["raw_text"])

        # Exclude mechanical capital transfer.
        if event_type == "资本公积转增":
            continue

        if event_type not in {
            "增资",
            "股权转让",
            "增资及股权转让",
        }:
            continue

        groups = extract_investor_groups(
            r["raw_text"]
        )

        events.append({
            "stock_code": code,
            "company": row["company_short_name"],

            "row_no": r["row_no"],
            "event_date": r["event_date"],
            "event_type": event_type,

            "event_label": extract_event_label(
                r["raw_text"],
                event_type
            ),

            "investor_groups_raw": groups,
            "investor_count_hint":
                count_hint(groups),

            "total_amount_wan":
                extract_amount(r["raw_text"]),

            "shares_issued":
                extract_shares(r["raw_text"]),

            "registered_capital_after":
                extract_capital_after(
                    r["raw_text"]
                ),

            "evidence_text":
                r["raw_text"][:5000],
        })

    out_file = (
        OUT_DIR
        / f"{code}_{row['company_short_name']}.jsonl"
    )

    with out_file.open(
        "w",
        encoding="utf-8"
    ) as f:
        for e in events:
            f.write(
                json.dumps(
                    e,
                    ensure_ascii=False
                )
                + "\n"
            )

    summary.append({
        "stock_code": code,
        "company": row["company_short_name"],
        "parsed_rows": len(parsed_rows),
        "target_events": len(events),
        "events_with_investors": sum(
            bool(e["investor_groups_raw"])
            for e in events
        ),
        "max_investor_count_hint": max(
            [
                e["investor_count_hint"]
                for e in events
            ],
            default=0
        ),
    })

    print(
        code,
        row["company_short_name"],
        f"rows={len(parsed_rows)}",
        f"events={len(events)}",
        f"with_investors="
        f"{summary[-1]['events_with_investors']}",
        f"max_investors="
        f"{summary[-1]['max_investor_count_hint']}",
    )


with OUT_SUMMARY.open(
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=list(summary[0].keys())
    )

    writer.writeheader()
    writer.writerows(summary)


print()
print("===== 688802 ROWS =====")

target = list(
    OUT_DIR.glob("688802_*.jsonl")
)

if not target:
    print("NO 688802 OUTPUT")

else:
    events = [
        json.loads(x)
        for x in target[0]
        .read_text(encoding="utf-8")
        .splitlines()
        if x.strip()
    ]

    for e in events:
        print()
        print(
            f"row={e['row_no']}",
            f"date={e['event_date']}",
            f"type={e['event_type']}",
            f"label={e['event_label']}",
            f"investors={e['investor_count_hint']}",
            f"amount={e['total_amount_wan']}",
            f"shares={e['shares_issued']}",
        )

        print(
            "  groups:",
            e["investor_groups_raw"]
        )

        print(
            "  evidence:",
            e["evidence_text"][:350]
        )


print()
print("Output:")
print(
    " ",
    OUT_SUMMARY.relative_to(ROOT)
)
