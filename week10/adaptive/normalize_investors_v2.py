#!/usr/bin/env python3

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

INPUT_DIR = ROOT / "week10/adaptive/summary_rows_v2"
OUT_DIR = ROOT / "week10/adaptive/investor_rows_v2"

OUT_DIR.mkdir(parents=True, exist_ok=True)


def compact_spaces(text):
    """
    Repair PDF line-wrap spaces inside Chinese names/text while
    preserving punctuation.
    """
    text = re.sub(r"\s+", " ", text)

    text = re.sub(
        r"(?<=[\u4e00-\u9fffA-Za-z0-9])\s+"
        r"(?=[\u4e00-\u9fffA-Za-z0-9])",
        "",
        text,
    )

    return text.strip()


def clean_group(raw):
    raw = compact_spaces(raw)

    # remove event label / numbering before first investor
    raw = re.sub(
        r"^报告期第.{0,50}?次增资\s*",
        "",
        raw,
    )

    raw = re.sub(
        r"^第.{0,40}?次增资\s*",
        "",
        raw,
    )

    # malformed flattened label such as:
    # 报告期第七1、... 次增资 ...
    raw = re.sub(
        r"^报告期第[^、]{0,20}?\d+[、.]",
        "",
        raw,
    )

    raw = re.sub(
        r"^\d+[、.]\s*",
        "",
        raw,
    )

    raw = raw.strip(" ，、；;:")

    return raw


def clause_groups(text):
    """
    Extract investor groups from price-based clauses.

    Handles multiple pricing groups in the same event row.
    """

    text = compact_spaces(text)

    groups = []

    # Split transaction subclauses first, instead of one giant regex.
    clauses = re.split(
        r"[；;]",
        text
    )

    for clause in clauses:

        if not (
            "认购" in clause
            and (
                "注册资本" in clause
                or "投资金额" in clause
            )
        ):
            continue

        # Pattern A:
        # A、B、C按照每1元注册资本...认购
        m = re.search(
            r"(?:^|\d+[、.])"
            r"(.+?)"
            r"按照每\s*1\s*元注册资本"
            r".*?(?:认购|出资认购)",
            clause,
        )

        if m:
            raw = clean_group(m.group(1))

            if raw:
                groups.append(raw)
                continue

        # Pattern B:
        # A、B、C各以人民币...元/每一元注册资本...认购
        m = re.search(
            r"(?:^|\d+[、.])"
            r"(.+?)"
            r"各以人民币[\d,.]+\s*元"
            r"[/／]\s*每一元注册资本"
            r".*?(?:认购|出资认购)",
            clause,
        )

        if m:
            raw = clean_group(m.group(1))

            if raw:
                groups.append(raw)

    return groups


def aggregate_group(text):
    """
    Extract long syndicate before:

      以合计 xxx 万元人民币的投资金额，认购...

    Allow whitespace inserted by PDF flattening:
      以 合计
      投资金 额
    """

    text = compact_spaces(text)

    anchor = re.search(
        r"以\s*合计\s*"
        r"[\d,]+(?:\.\d+)?\s*万元人民币的投资金额"
        r".{0,100}?认购",
        text,
    )

    if not anchor:
        return ""

    prefix = text[:anchor.start()]

    # Prefer text following transaction body marker "1、".
    markers = list(
        re.finditer(
            r"(?:^|\s)1[、.]",
            prefix
        )
    )

    if markers:
        prefix = prefix[
            markers[-1].end():
        ]

    else:
        # fallback: remove event label
        prefix = re.sub(
            r"^报告期第.{0,80}?次增资\s*",
            "",
            prefix,
        )

    raw = clean_group(prefix)

    return raw


def split_names(raw):

    if not raw:
        return []

    raw = compact_spaces(raw)

    pieces = re.split(
        r"[、，,；;]",
        raw
    )

    out = []

    for p in pieces:

        name = compact_spaces(p)
        name = name.strip(" ：:、，,；;")

        if not name:
            continue

        # Remove remaining structural prefixes.
        name = re.sub(
            r"^(?:报告期第.{0,30}?次增资|"
            r"第.{0,20}?次增资|"
            r"\d+[、.])",
            "",
            name,
        ).strip()

        if not name:
            continue

        # obvious body fragments, not investor names
        bad_terms = [
            "注册资本",
            "投资金额",
            "认购公司",
            "发行新股",
            "本次增资",
            "资本公积",
            "超出部分",
            "人民币的",
        ]

        if any(x in name for x in bad_terms):
            continue

        if len(name) > 80:
            continue

        if name not in out:
            out.append(name)

    return out


def extract_groups(text):

    groups = clause_groups(text)

    agg = aggregate_group(text)

    if agg and agg not in groups:
        groups.append(agg)

    # deterministic group dedupe
    seen = set()
    result = []

    for g in groups:
        key = re.sub(r"\s+", "", g)

        if key in seen:
            continue

        seen.add(key)
        result.append(g)

    return result


def repair_shares(event):
    """
    Stage 4B row 9 may miss shares because PDF inserted
    whitespace between '发行' and '新股'.
    """

    if event.get("shares_issued") is not None:
        return event["shares_issued"]

    text = compact_spaces(
        event.get("evidence_text", "")
    )

    patterns = [
        r"认购公司(?:本次)?发行\s*新股"
        r"\s*([\d,]+(?:\.\d+)?)\s*股",

        r"认购公司发行\s*新股"
        r"\s*([\d,]+(?:\.\d+)?)\s*股",
    ]

    for p in patterns:
        m = re.search(p, text)

        if m:
            return float(
                m.group(1).replace(",", "")
            )

    return None


print()
print("===== INVESTOR NORMALIZATION V2 =====")

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

    output = []

    for e in events:

        groups = extract_groups(
            e.get("evidence_text", "")
        )

        investors = []

        for g in groups:
            investors.extend(
                split_names(g)
            )

        # deterministic investor dedupe
        seen = set()
        investors2 = []

        for name in investors:
            if name in seen:
                continue

            seen.add(name)
            investors2.append(name)

        x = dict(e)

        x["investor_groups_v3"] = groups
        x["investors_normalized_v2"] = investors2
        x["investor_count_v3"] = len(investors2)

        x["shares_issued"] = repair_shares(x)

        output.append(x)

    out = OUT_DIR / path.name

    with out.open(
        "w",
        encoding="utf-8"
    ) as f:
        for x in output:
            f.write(
                json.dumps(
                    x,
                    ensure_ascii=False
                )
                + "\n"
            )


print()
print("===== 688802 INVESTOR CHECK V2 =====")

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
            f"count={e['investor_count_v3']}",
            f"amount={e['total_amount_wan']}",
            f"shares={e['shares_issued']}",
        )

        print(
            "groups:",
            len(e["investor_groups_v3"])
        )

        for i, g in enumerate(
            e["investor_groups_v3"],
            1
        ):
            print(
                f"  group{i}:",
                g[:500]
            )

        print(
            "investors:",
            " | ".join(
                e["investors_normalized_v2"]
            )
        )


print()
print("Output:")
print(
    " ",
    OUT_DIR.relative_to(ROOT)
)
