from pathlib import Path
import re
import csv
import json

ROOT = Path(".")
OUT = ROOT / "week10/adaptive/long_syndicate_v1"
OUT.mkdir(parents=True, exist_ok=True)

# Stage 4E initially targets the blind long-syndicate case.
TARGETS = {
    "688795": {
        "company": "摩尔线程",
        "patterns": [
            "week1/review/*688795*.md",
            "week*/**/*688795*.md",
        ],
    }
}


def locate_file(patterns):
    seen = set()

    for pat in patterns:
        for p in ROOT.glob(pat):
            if p.is_file() and p not in seen:
                seen.add(p)
                return p

    # fallback
    for p in ROOT.rglob("*.md"):
        if "688795" in p.name:
            return p

    return None


def norm_space(s):
    s = s.replace("\u3000", " ")
    s = s.replace("\xa0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    return s


def clean_name(s):
    s = norm_space(s).strip()

    # repair line-wrap whitespace inside Chinese organization names
    s = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", s)

    s = s.strip(" 、，,；;。:：()（）\"“”'")

    return s


def split_names(raw):
    raw = norm_space(raw)

    # MinerU line wraps should not split names.
    raw = re.sub(
        r"(?<=[\u4e00-\u9fff])\s*\n\s*(?=[\u4e00-\u9fff])",
        "",
        raw,
    )

    raw = raw.replace("\n", "")

    # final conjunction
    raw = re.sub(r"[及和]\s*(?=[^、，,；;]{2,40}$)", "、", raw)

    parts = re.split(r"[、，,；;]", raw)

    names = []

    for x in parts:
        x = clean_name(x)

        if not x:
            continue

        # reject obvious narrative fragments
        if any(k in x for k in [
            "期间",
            "签订",
            "协议",
            "以下简称",
            "共计",
            "主体",
            "公司",
            "召开",
            "股东会",
        ]):
            continue

        if len(x) > 40:
            continue

        if x not in names:
            names.append(x)

    return names


def parse_alias_definitions(text):
    """
    Capture narrative syndicate definitions such as:

      A、B、C……及Z（以下简称“Pre-IPO轮股东”）共计38家主体

    The PDF-to-Markdown representation may insert arbitrary spaces or
    line breaks inside '以下简称', the alias, and '共计38家主体'.
    """

    aliases = []

    # --------------------------------------------------
    # Normalize only structural phrases.
    # Do NOT globally remove whitespace because that can
    # destroy member-name boundaries.
    # --------------------------------------------------

    normalized = text

    normalized = re.sub(
        r"以\s*下\s*简\s*称",
        "以下简称",
        normalized
    )

    normalized = re.sub(
        r"共\s*计",
        "共计",
        normalized
    )

    normalized = re.sub(
        r"家\s*主\s*体",
        "家主体",
        normalized
    )

    # Main definition pattern.
    #
    # Instead of tightly constraining the character class of the member
    # list, anchor on:
    #
    #   （以下简称“alias”）共计 N 家主体
    #
    # and then recover the member-list sentence immediately before it.
    alias_re = re.compile(
        r"[（(]\s*以下简称\s*"
        r"[“\"'‘]?"
        r"(?P<alias>[^”\"'’）)]{2,60}?)"
        r"[”\"'’]?"
        r"\s*[）)]"
        r"\s*共计\s*"
        r"(?P<count>\d+)\s*家(?:主体)?",
        re.S,
    )

    for m in alias_re.finditer(normalized):

        # Look backwards within a bounded region.
        lo = max(0, m.start() - 3500)
        prefix = normalized[lo:m.start()]

        # The member list should be the latest sentence-like segment.
        # Prefer Chinese sentence punctuation, then paragraph boundary.
        candidates = [
            prefix.rfind("。"),
            prefix.rfind("；"),
            prefix.rfind("\n\n"),
        ]

        cut = max(candidates)

        if cut >= 0:
            raw = prefix[cut + 1:]
        else:
            raw = prefix

        # Remove leading date/introduction, e.g.
        # 2024 年11-12 月期间，
        raw = re.sub(
            r"^\s*20\d{2}\s*年"
            r"[^，,。；;]{0,50}"
            r"[，,]\s*",
            "",
            raw,
        )

        # Remove common narrative lead-ins.
        raw = re.sub(
            r"^\s*(?:期间|其中|包括|分别为|具体为)\s*",
            "",
            raw,
        )

        raw = raw.strip()

        members = split_names(raw)
        declared = int(m.group("count"))

        aliases.append({
            "alias": clean_name(m.group("alias")),
            "declared_count": declared,
            "members": members,
            "raw_members": raw,
            "start": lo + (
                cut + 1 if cut >= 0 else 0
            ),
            "end": m.end(),
        })

    # --------------------------------------------------
    # Fallback:
    # if alias regex still misses, detect a "共计N家主体"
    # sentence and search the immediately preceding text
    # for an alias phrase.
    # --------------------------------------------------

    if not aliases:

        count_re = re.compile(
            r"共计\s*(?P<count>\d+)\s*家(?:主体)?"
        )

        for cm in count_re.finditer(normalized):

            lo = max(0, cm.start() - 3500)
            seg = normalized[lo:cm.end()]

            am = re.search(
                r"[（(]\s*以下简称\s*"
                r"[“\"'‘]?"
                r"(?P<alias>[^”\"'’）)]{2,60}?)"
                r"[”\"'’]?"
                r"\s*[）)]",
                seg,
                re.S,
            )

            if not am:
                continue

            before_alias = seg[:am.start()]

            cut = max(
                before_alias.rfind("。"),
                before_alias.rfind("；"),
                before_alias.rfind("\n\n"),
            )

            raw = (
                before_alias[cut + 1:]
                if cut >= 0
                else before_alias
            )

            raw = re.sub(
                r"^\s*20\d{2}\s*年"
                r"[^，,。；;]{0,50}"
                r"[，,]\s*",
                "",
                raw,
            )

            raw = raw.strip()

            members = split_names(raw)
            declared = int(cm.group("count"))

            aliases.append({
                "alias": clean_name(am.group("alias")),
                "declared_count": declared,
                "members": members,
                "raw_members": raw,
                "start": lo + (
                    cut + 1 if cut >= 0 else 0
                ),
                "end": cm.end(),
            })

    return aliases

def find_event_for_alias(text, alias_obj):
    alias = re.escape(alias_obj["alias"])

    # Search forward from alias definition.
    start = alias_obj["end"]
    window = text[start:start + 3500]

    # Need a genuine investment action.
    action = re.search(
        rf"{alias}.{{0,500}}?"
        r"(?:认购|增资|新增股份|新增注册资本)",
        window,
        re.S,
    )

    if not action:
        return None

    evidence_start = max(0, alias_obj["start"] - 200)
    evidence_end = min(
        len(text),
        start + action.end() + 900
    )

    evidence = text[evidence_start:evidence_end]

    # date
    dates = re.findall(
        r"(20\d{2})\s*年\s*(\d{1,2})\s*月",
        evidence,
    )

    date = None
    if dates:
        # Prefer the latest explicit month around the action.
        y, m = dates[-1]
        date = f"{y}-{int(m):02d}"

    # investment amount
    amount = None

    amount_patterns = [
        r"合计\s*([\d,]+(?:\.\d+)?)\s*万元(?:人民币)?(?:的投资金额)?(?:认购)?",
        r"以\s*合计\s*([\d,]+(?:\.\d+)?)\s*万元(?:人民币)?\s*认购",
    ]

    for p in amount_patterns:
        mm = re.search(p, evidence)
        if mm:
            amount = float(mm.group(1).replace(",", ""))
            break

    # shares / new registered capital
    shares = None

    share_patterns = [
        r"新增股份\s*([\d,]+(?:\.\d+)?)\s*万股",
        r"发行新股\s*([\d,]+(?:\.\d+)?)\s*股",
        r"认购公司(?:本次)?发行新股\s*([\d,]+(?:\.\d+)?)\s*股",
    ]

    for p in share_patterns:
        mm = re.search(p, evidence)
        if mm:
            shares = float(mm.group(1).replace(",", ""))
            break

    return {
        "date": date,
        "amount": amount,
        "shares": shares,
        "evidence": norm_space(evidence),
    }


rows = []
diagnostics = []

for code, cfg in TARGETS.items():

    p = locate_file(cfg["patterns"])

    if p is None:
        print(code, cfg["company"], "FILE NOT FOUND")
        continue

    text = p.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    aliases = parse_alias_definitions(text)

    print()
    print("=" * 70)
    print(code, cfg["company"])
    print("source:", p)
    print("aliases:", len(aliases))
    print("=" * 70)

    for a in aliases:

        event = find_event_for_alias(text, a)

        print()
        print(
            "alias=",
            a["alias"],
            "declared=",
            a["declared_count"],
            "parsed=",
            len(a["members"]),
        )

        print("members:")
        print(" | ".join(a["members"]))

        if not event:
            print("event: NOT FOUND")
            continue

        print(
            "event:",
            event["date"],
            "amount=",
            event["amount"],
            "shares=",
            event["shares"],
        )

        # High precision gate:
        # the parsed member count should agree with declared N.
        count_ok = (
            len(a["members"]) == a["declared_count"]
        )

        diagnostics.append({
            "code": code,
            "company": cfg["company"],
            "alias": a["alias"],
            "declared_count": a["declared_count"],
            "parsed_count": len(a["members"]),
            "count_ok": count_ok,
            "date": event["date"],
            "amount": event["amount"],
            "shares": event["shares"],
        })

        if not count_ok:
            print(
                "⚠️ count mismatch — candidate not emitted:",
                len(a["members"]),
                "!=",
                a["declared_count"],
            )
            continue

        for investor in a["members"]:

            rows.append({
                "code": code,
                "company": cfg["company"],
                "date": event["date"] or "",
                "event_type": "增资",
                "investor": investor,
                "amount": (
                    event["amount"]
                    if event["amount"] is not None
                    else ""
                ),
                "shares": (
                    event["shares"]
                    if event["shares"] is not None
                    else ""
                ),
                "source_module": "long_syndicate_alias_v1",
                "alias": a["alias"],
                "declared_count": a["declared_count"],
                "evidence": event["evidence"],
            })


csv_path = OUT / "long_syndicate_rows_v1.csv"

fields = [
    "code",
    "company",
    "date",
    "event_type",
    "investor",
    "amount",
    "shares",
    "source_module",
    "alias",
    "declared_count",
    "evidence",
]

with csv_path.open(
    "w",
    encoding="utf-8-sig",
    newline=""
) as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)


diag_path = OUT / "diagnostics_v1.json"

diag_path.write_text(
    json.dumps(
        diagnostics,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


print()
print("=" * 70)
print("LONG-SYNDICATE RESULT")
print("=" * 70)
print("rows:", len(rows))

for code in TARGETS:
    rr = [x for x in rows if x["code"] == code]

    print(
        code,
        "rows=",
        len(rr),
        "unique_investors=",
        len(set(x["investor"] for x in rr)),
    )

print()
print("Output:")
print(" ", csv_path)
print(" ", diag_path)
