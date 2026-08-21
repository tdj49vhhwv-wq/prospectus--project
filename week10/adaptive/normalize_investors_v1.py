#!/usr/bin/env python3

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

INPUT_DIR = ROOT / "week10/adaptive/summary_rows_v2"
OUT_DIR = ROOT / "week10/adaptive/investor_rows_v1"

OUT_DIR.mkdir(parents=True, exist_ok=True)


def normalize_whitespace(name):
    """
    Repair PDF line-wrap spaces inside organization names.

    Examples:
      嘉 兴普超 -> 嘉兴普超
      经 乾二号 -> 经乾二号
      经纬 厦门 -> 经纬厦门
      新华 文泰 -> 新华文泰

    Keep separator punctuation outside this function.
    """

    name = name.strip()

    # collapse ordinary whitespace
    name = re.sub(r"\s+", " ", name)

    # remove spaces between Chinese characters / Chinese + digits
    name = re.sub(
        r"(?<=[\u4e00-\u9fffA-Za-z0-9])\s+"
        r"(?=[\u4e00-\u9fffA-Za-z0-9])",
        "",
        name
    )

    return name.strip()


def remove_event_prefix(text):
    """
    Remove flattened event labels that may precede the first investor.
    """

    text = re.sub(
        r"^报告期第.{0,40}?次增资\s*",
        "",
        text
    )

    text = re.sub(
        r"^第.{0,30}?次增资\s*",
        "",
        text
    )

    text = re.sub(
        r"^\d+[、.]\s*",
        "",
        text
    )

    return text.strip()


def extract_all_groups(text):
    """
    Extract every investor group from one row.

    Handles:
      A、B、C 按照每1元注册资本...
      A、B、C 各以人民币...元/每一元注册资本...
      A、B、C 以合计xxx万元人民币的投资金额，认购...
    """

    groups = []

    patterns = [
        re.compile(
            r"(?:^|[；;])\s*"
            r"(?:\d+[、.]\s*)?"
            r"(.{1,3000}?)"
            r"按照每\s*1\s*元注册资本"
            r"\s*[\d,.]+\s*元的价格"
            r"[^；;。]{0,250}?"
            r"(?:认购|出资认购)",
            re.S
        ),

        re.compile(
            r"(?:^|[；;])\s*"
            r"(?:\d+[、.]\s*)?"
            r"(.{1,3000}?)"
            r"各以人民币\s*[\d,.]+\s*元"
            r"\s*[/／]\s*每一元注册资本"
            r"[^；;。]{0,250}?"
            r"(?:认购|出资认购)",
            re.S
        ),

        re.compile(
            r"(?:^|[；;])\s*"
            r"(?:\d+[、.]\s*)?"
            r"(.{1,4000}?)"
            r"以合计\s*[\d,]+(?:\.\d+)?\s*万元人民币的投资金额"
            r"[^；;。]{0,180}?"
            r"认购",
            re.S
        ),
    ]

    for pat in patterns:
        for m in pat.finditer(text):
            raw = m.group(1).strip()

            raw = remove_event_prefix(raw)

            # remove body residue accidentally captured before investor list
            raw = re.sub(
                r"^.*?(?:1、|1\.)",
                "",
                raw,
                count=1
            )

            raw = raw.strip(" ，、；;:")

            if not raw:
                continue

            # prevent grabbing narrative paragraphs
            if len(raw) > 3500:
                continue

            if raw not in groups:
                groups.append(raw)

    return groups


def split_group(raw):
    """
    Split one group into disclosed investor names.
    """

    raw = normalize_whitespace(raw)

    pieces = re.split(
        r"[、，,；;]",
        raw
    )

    out = []

    for p in pieces:
        name = normalize_whitespace(p)

        # strip transaction / row residue
        name = re.sub(
            r"^(?:\d+[、.]|"
            r"报告期第.{0,30}?次增资|"
            r"第.{0,20}?次增资)",
            "",
            name
        ).strip()

        # obvious non-name fragments
        if not name:
            continue

        if any(
            x in name
            for x in [
                "注册资本",
                "投资金额",
                "本次增资",
                "发行人新增",
                "超出部分",
                "计入公司资本公积",
                "本次增资后",
            ]
        ):
            continue

        if len(name) > 80:
            continue

        if name not in out:
            out.append(name)

    return out


def event_key(e):
    return (
        e.get("stock_code", ""),
        e.get("event_date", ""),
        e.get("row_no", ""),
        e.get("event_type", ""),
    )


print()
print("===== INVESTOR NORMALIZATION =====")

all_company_outputs = []

for path in sorted(INPUT_DIR.glob("*.jsonl")):

    events = [
        json.loads(x)
        for x in path.read_text(
            encoding="utf-8"
        ).splitlines()
        if x.strip()
    ]

    if not events:
        continue

    normalized_events = []

    for e in events:

        groups = extract_all_groups(
            e.get("evidence_text", "")
        )

        investors = []

        for g in groups:
            investors.extend(
                split_group(g)
            )

        # deterministic dedupe
        seen = set()
        deduped = []

        for name in investors:
            if name not in seen:
                seen.add(name)
                deduped.append(name)

        out = dict(e)

        out["investor_groups_v2"] = groups
        out["investors_normalized"] = deduped
        out["investor_count_v2"] = len(deduped)

        normalized_events.append(out)

    out_path = (
        OUT_DIR
        / path.name
    )

    with out_path.open(
        "w",
        encoding="utf-8"
    ) as f:
        for e in normalized_events:
            f.write(
                json.dumps(
                    e,
                    ensure_ascii=False
                )
                + "\n"
            )

    code = events[0]["stock_code"]
    company = events[0]["company"]

    print()
    print(code, company)

    for e in normalized_events:
        if e["event_type"] != "增资":
            continue

        print(
            f"  row={e['row_no']}",
            f"date={e['event_date']}",
            f"investors={e['investor_count_v2']}",
        )

        if e["investors_normalized"]:
            print(
                "   ",
                " | ".join(
                    e["investors_normalized"][:20]
                )
            )

    all_company_outputs.append(
        normalized_events
    )


print()
print("===== 688802 INVESTOR CHECK =====")

targets = list(
    OUT_DIR.glob("688802_*.jsonl")
)

if not targets:
    print("NO 688802 OUTPUT")

else:
    events = [
        json.loads(x)
        for x in targets[0]
        .read_text(encoding="utf-8")
        .splitlines()
        if x.strip()
    ]

    for e in events:
        if e["event_type"] != "增资":
            continue

        print()
        print(
            f"row={e['row_no']}",
            f"date={e['event_date']}",
            f"count={e['investor_count_v2']}",
            f"amount={e['total_amount_wan']}",
            f"shares={e['shares_issued']}",
        )

        print(
            "investors:",
            " | ".join(
                e["investors_normalized"]
            )
        )


print()
print("Output:")
print(
    " ",
    OUT_DIR.relative_to(ROOT)
)
