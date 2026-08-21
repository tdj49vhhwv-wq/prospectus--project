#!/usr/bin/env python3

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

INPUT_DIR = ROOT / "week10/adaptive/summary_blocks_v2"
OUT_DIR = ROOT / "week10/adaptive/summary_events_v1"
OUT_SUMMARY = ROOT / "week10/adaptive/summary_event_summary_v1.csv"

OUT_DIR.mkdir(parents=True, exist_ok=True)


DATE_PATTERNS = [
    re.compile(
        r"((?:19|20)\d{2})\s*年\s*"
        r"(\d{1,2})\s*月\s*(\d{1,2})\s*日"
    ),
    re.compile(
        r"((?:19|20)\d{2})\s*年\s*"
        r"(\d{1,2})\s*月"
    ),
]

EVENT_TERMS = [
    "增资扩股",
    "增资",
    "增加注册资本",
    "定向发行",
    "发行新股",
    "股权转让",
    "股份转让",
    "整体变更",
]

INVESTOR_ACTION_TERMS = [
    "认购",
    "认缴",
    "投资金额",
    "增资金额",
    "新增股东",
]

NON_EVENT_TERMS = [
    "验资报告",
    "验资情况",
    "出资瑕疵",
    "对赌协议",
    "特殊权利安排",
    "股权激励",
    "股份支付",
]


def normalize_space(text):
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_date(text):
    for pat in DATE_PATTERNS:
        m = pat.search(text)

        if not m:
            continue

        vals = m.groups()

        if len(vals) == 3:
            y, mo, d = vals
            return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"

        y, mo = vals
        return f"{int(y):04d}-{int(mo):02d}"

    return ""


def classify_event(text):
    if (
        ("增资" in text or "增加注册资本" in text)
        and ("股权转让" in text or "股份转让" in text)
    ):
        return "增资及股权转让"

    if (
        "增资" in text
        or "增加注册资本" in text
        or "发行新股" in text
        or "定向发行" in text
    ):
        return "增资"

    if "股权转让" in text or "股份转让" in text:
        return "股权转让"

    if "整体变更" in text:
        return "整体变更"

    return ""


def extract_number(text, patterns):
    for pat in patterns:
        m = re.search(pat, text)

        if m:
            try:
                return float(
                    m.group(1).replace(",", "")
                )
            except Exception:
                pass

    return None


def extract_amount(text):
    return extract_number(
        text,
        [
            r"合计\s*([\d,]+(?:\.\d+)?)\s*万元[^。；]{0,20}投资",
            r"合计\s*([\d,]+(?:\.\d+)?)\s*万元",
            r"投资金额[^。\d]{0,15}([\d,]+(?:\.\d+)?)\s*万元",
            r"增资金额[^。\d]{0,15}([\d,]+(?:\.\d+)?)\s*万元",
            r"认购金额[^。\d]{0,15}([\d,]+(?:\.\d+)?)\s*万元",
        ],
    )


def extract_shares(text):
    value = extract_number(
        text,
        [
            r"认购[^。；]{0,80}?([\d,]+(?:\.\d+)?)\s*股",
            r"发行新股[^。；]{0,80}?([\d,]+(?:\.\d+)?)\s*股",
            r"新增股份[^。；]{0,80}?([\d,]+(?:\.\d+)?)\s*股",
            r"认购数量[^。\d]{0,15}([\d,]+(?:\.\d+)?)",
        ],
    )

    return value


def extract_registered_capital(text):
    return extract_number(
        text,
        [
            r"注册资本(?:为|增至|增加至)\s*"
            r"([\d,]+(?:\.\d+)?)\s*(?:万元|元)",
            r"变更后注册资本[^。\d]{0,20}"
            r"([\d,]+(?:\.\d+)?)",
        ],
    )


def extract_investor_list(text):
    """
    Extract the raw investor-name list from one logical event unit.

    This stage intentionally preserves aliases as disclosed.
    Name normalization happens in Stage 4C.
    """

    patterns = [
        # 沐曦式：
        # A、B、C按照每1元注册资本...以货币出资认购...
        re.compile(
            r"(?:^|[：:；;。])\s*"
            r"(?:\d+[、.]\s*)?"
            r"([^。；]{2,3000}?)"
            r"按照每\s*1\s*元注册资本"
            r"[^。；]{0,400}?"
            r"(?:认购|出资认购)"
        ),

        # multiple price groups:
        # A、B按照...认购...
        re.compile(
            r"(?:^|[：:；;。])\s*"
            r"(?:\d+[、.]\s*)?"
            r"([^。；]{2,3000}?)"
            r"(?:各?以人民币)?"
            r"[\d,.]+\s*元[/／]每一元注册资本"
            r"[^。；]{0,350}?"
            r"(?:认购|增资)"
        ),

        # long group + aggregate amount
        re.compile(
            r"([^。；]{5,3000}?)"
            r"以合计[\d,]+(?:\.\d+)?\s*万元"
            r"[^。；]{0,120}?"
            r"(?:认购|增资)"
        ),

        re.compile(
            r"(?:由|新增股东为|投资方为)"
            r"([^。；]{5,3000}?)"
            r"(?:认购|增资|出资)"
        ),

        re.compile(
            r"([^。；]{5,3000}?)"
            r"(?:共同认购|共同增资)"
        ),
    ]

    best = ""

    for pat in patterns:
        for m in pat.finditer(text):
            raw = normalize_space(m.group(1))

            # Remove table row labels / serial-number residue.
            raw = re.sub(
                r"^(?:\d+\s+)?"
                r"(?:报告期第[^ ]+次(?:增资|股权转让)\s*)?",
                "",
                raw
            )

            raw = re.sub(
                r"^(?:序号|时间|股权变动|股权变动情况|"
                r"本次|本轮|新增股份由)\s*",
                "",
                raw
            )

            raw = raw.strip(" ，、;；:")

            # Require list-like/entity-like content.
            if (
                raw
                and len(raw) <= 2500
                and (
                    "、" in raw
                    or "，" in raw
                    or "," in raw
                    or len(raw) <= 80
                )
            ):
                if len(raw) > len(best):
                    best = raw

    return best

def estimate_investor_count(raw):
    if not raw:
        return 0

    pieces = [
        x.strip()
        for x in re.split(
            r"[、，,；;]",
            raw
        )
        if x.strip()
    ]

    return len(pieces)


def score_event(text, event_type, event_date, investors, amount, shares):
    score = 0
    reasons = []

    if event_type:
        score += 2
        reasons.append("event_type")

    if event_date:
        score += 2
        reasons.append("date")

    action_hits = sum(
        1 for x in INVESTOR_ACTION_TERMS
        if x in text
    )

    if action_hits:
        score += min(2, action_hits)
        reasons.append(
            f"investor_actions={action_hits}"
        )

    if investors:
        score += 3
        reasons.append("investor_list")

    if amount is not None:
        score += 2
        reasons.append("amount")

    if shares is not None:
        score += 2
        reasons.append("shares")

    if any(x in text for x in NON_EVENT_TERMS):
        score -= 3
        reasons.append("non_event_penalty")

    return score, reasons


def split_candidate_into_units(text):
    """
    Split flattened equity-history summary tables into logical event rows.

    Prefer row-like boundaries:
      [序号] [YYYY年M月] [报告期第X次增资/股权转让]

    Never prepend text from the previous event, because doing so contaminates
    amount/share/investor fields across adjacent rows.
    """

    text = text.replace("\r", "\n")

    # Normalize page/header noise but preserve semantic text.
    text = re.sub(
        r"##\s*第\d+页\s+[^\\n]{0,120}?招股说明书\s+1-1-\d+",
        " ",
        text
    )

    # A logical row normally begins with:
    # optional serial number + year/month + event label.
    row_re = re.compile(
        r"(?=(?:^|\s)"
        r"(?:\d{1,2}\s+)?"
        r"(?:19|20)\d{2}\s*年\s*\d{1,2}\s*月"
        r"(?:\s*\d{1,2}\s*日)?\s*"
        r"(?:报告期[^。；]{0,50}?"
        r"(?:增资|股权转让|股份转让|资本公积转增)"
        r"|第[^。；]{0,30}?(?:增资|股权转让)"
        r"|[^。；]{0,20}?(?:增资|股权转让|股份转让)))",
        re.S
    )

    starts = [m.start() for m in row_re.finditer(text)]

    if not starts:
        # fallback to date-only boundaries, without backward overlap
        date_re = re.compile(
            r"(?=(?:19|20)\d{2}\s*年\s*\d{1,2}\s*月)"
        )
        starts = [m.start() for m in date_re.finditer(text)]

    starts = sorted(set(starts))

    if not starts:
        return [text]

    units = []

    # Keep prefix separately only if it itself contains a valid transaction.
    if starts[0] > 0:
        prefix = text[:starts[0]].strip()
        if (
            len(prefix) >= 40
            and any(x in prefix for x in (
                "增资", "股权转让", "发行新股"
            ))
        ):
            units.append(prefix)

    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(text)

        unit = text[start:end].strip()

        if len(unit) >= 40:
            units.append(unit)

    return units

def parse_company(path):
    data = json.loads(
        path.read_text(encoding="utf-8")
    )

    events = []

    for candidate_id, candidate in enumerate(
        data.get("candidates", []),
        1
    ):
        text = candidate.get("text", "")

        units = split_candidate_into_units(text)

        for unit_id, unit in enumerate(units, 1):
            clean = normalize_space(unit)

            event_type = classify_event(clean)

            if not event_type:
                continue

            # only continue when transaction language exists
            if not any(
                term in clean
                for term in EVENT_TERMS
            ):
                continue

            event_date = parse_date(clean)
            investors = extract_investor_list(clean)
            amount = extract_amount(clean)
            shares = extract_shares(clean)
            capital_after = extract_registered_capital(clean)

            score, reasons = score_event(
                clean,
                event_type,
                event_date,
                investors,
                amount,
                shares,
            )

            # candidate layer: moderately permissive
            if score < 5:
                continue

            events.append({
                "stock_code":
                    data["stock_code"],
                "company":
                    data["company"],

                "candidate_id":
                    candidate_id,
                "unit_id":
                    unit_id,

                "event_date":
                    event_date,
                "event_type":
                    event_type,

                "investor_list_raw":
                    investors,

                "investor_count_hint":
                    estimate_investor_count(
                        investors
                    ),

                "total_amount_wan":
                    amount,

                "shares_issued":
                    shares,

                "registered_capital_after":
                    capital_after,

                "confidence_score":
                    score,

                "confidence_reasons":
                    reasons,

                "evidence_text":
                    clean[:4000],
            })

    # deterministic dedupe
    dedup = {}

    for e in events:
        key = (
            e["event_date"],
            e["event_type"],
            re.sub(
                r"\s+",
                "",
                e["investor_list_raw"]
            )[:300],
            e["total_amount_wan"],
            e["shares_issued"],
        )

        old = dedup.get(key)

        if (
            old is None
            or e["confidence_score"]
            > old["confidence_score"]
        ):
            dedup[key] = e

    return list(dedup.values())


print()
print("===== SUMMARY EVENT PARSING =====")

summary = []

for path in sorted(INPUT_DIR.glob("*.json")):

    events = parse_company(path)

    if not events:
        continue

    first = events[0]

    out_path = (
        OUT_DIR
        / f"{first['stock_code']}_{first['company']}.jsonl"
    )

    with out_path.open(
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

    with_investors = sum(
        bool(e["investor_list_raw"])
        for e in events
    )

    dated = sum(
        bool(e["event_date"])
        for e in events
    )

    summary.append({
        "stock_code":
            first["stock_code"],
        "company":
            first["company"],
        "event_candidates":
            len(events),
        "with_date":
            dated,
        "with_investor_list":
            with_investors,
        "max_investor_count_hint":
            max(
                [
                    e["investor_count_hint"]
                    for e in events
                ],
                default=0
            ),
    })

    print(
        first["stock_code"],
        first["company"],
        f"events={len(events)}",
        f"dated={dated}",
        f"investor_lists={with_investors}",
        f"max_investors={summary[-1]['max_investor_count_hint']}",
    )


with OUT_SUMMARY.open(
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:

    fields = [
        "stock_code",
        "company",
        "event_candidates",
        "with_date",
        "with_investor_list",
        "max_investor_count_hint",
    ]

    writer = csv.DictWriter(
        f,
        fieldnames=fields
    )

    writer.writeheader()
    writer.writerows(summary)


print()
print("===== 688802 PREVIEW =====")

target = list(
    OUT_DIR.glob("688802_*.jsonl")
)

if not target:
    print("NO 688802 OUTPUT")

else:
    rows = [
        json.loads(x)
        for x in target[0]
        .read_text(encoding="utf-8")
        .splitlines()
        if x.strip()
    ]

    for e in rows[:10]:
        print()
        print(
            "date=",
            e["event_date"],
            "type=",
            e["event_type"],
            "investors=",
            e["investor_count_hint"],
            "amount=",
            e["total_amount_wan"],
            "shares=",
            e["shares_issued"],
            "score=",
            e["confidence_score"],
        )

        print(
            "list:",
            e["investor_list_raw"][:400]
        )

        print(
            "evidence:",
            e["evidence_text"][:500]
        )


print()
print("Output:")
print(
    " ",
    OUT_SUMMARY.relative_to(ROOT)
)
