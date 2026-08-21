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
    Keep raw investor list first.
    Stage 4C will split and normalize names.
    """

    patterns = [
        re.compile(
            r"([^\n。；]{5,3000}?)"
            r"以合计[\d,]+(?:\.\d+)?\s*万元"
            r"[^。；]{0,100}?"
            r"(?:认购|增资)"
        ),

        re.compile(
            r"(?:由|新增股东为|投资方为)"
            r"([^\n。；]{5,3000}?)"
            r"(?:认购|增资|出资)"
        ),

        re.compile(
            r"([^\n。；]{5,3000}?)"
            r"(?:共同认购|共同增资)"
        ),
    ]

    for pat in patterns:
        m = pat.search(text)

        if not m:
            continue

        raw = normalize_space(m.group(1))

        # remove common structural prefixes
        raw = re.sub(
            r"^(?:序号|时间|股权变动|股权变动情况|"
            r"本次|本轮|新增股份由)",
            "",
            raw,
        )

        # avoid swallowing unrelated narrative
        if len(raw) > 2500:
            raw = raw[-2500:]

        return raw.strip(" ，、;；:")

    return ""


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
    Flattened PDF tables may have one logical event spread over many lines.
    Segment using dates and numbered transaction headings.
    """

    text = text.replace("\r", "\n")

    markers = []

    date_re = re.compile(
        r"(?:19|20)\d{2}\s*年\s*\d{1,2}\s*月"
    )

    for m in date_re.finditer(text):
        markers.append(m.start())

    # also detect "第X次增资" / numbered event rows
    event_marker = re.compile(
        r"(?:第\s*[一二三四五六七八九十\d]+\s*次"
        r"(?:增资|股权转让)|"
        r"\d+\s*[、.]\s*[^。\n]{0,40}"
        r"(?:增资|股权转让))"
    )

    for m in event_marker.finditer(text):
        markers.append(m.start())

    markers = sorted(set(markers))

    if not markers:
        return [text]

    units = []

    for i, start in enumerate(markers):
        end = (
            markers[i + 1]
            if i + 1 < len(markers)
            else len(text)
        )

        # include some preceding context because flattened
        # tables often put the row label before the date.
        lo = max(0, start - 250)

        unit = text[lo:end]

        if len(unit.strip()) >= 40:
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
