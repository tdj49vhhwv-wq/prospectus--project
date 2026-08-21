#!/usr/bin/env python3

import csv
import json
import re
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[2]

UNIVERSE = (
    ROOT
    / "week10"
    / "universe"
    / "prospectus_universe_v1_seed.csv"
)

OUT_CSV = (
    ROOT
    / "week10"
    / "taxonomy"
    / "structure_features_v1.csv"
)

FEATURE_DIR = (
    ROOT
    / "week10"
    / "profiler"
    / "features"
)

FEATURE_DIR.mkdir(parents=True, exist_ok=True)


EQUITY_TERMS = [
    "历史沿革",
    "股本演变",
    "股本形成",
    "股权演变",
    "历次增资",
    "增资",
    "股权转让",
    "整体变更",
    "设立",
    "股份制改造",
    "发行融资",
]

RESTRUCTURING_TERMS = [
    "重大资产重组",
    "重组",
    "吸收合并",
    "资产置换",
    "业务重组",
    "同一控制下",
]

INVESTOR_TERMS = [
    "投资",
    "基金",
    "创投",
    "资本",
    "合伙企业",
    "认购",
    "认缴",
    "增资方",
    "新增股东",
]

VIE_TERMS = [
    "VIE",
    "协议控制",
    "可变利益实体",
    "境外架构",
    "红筹",
    "返程投资",
    "WFOE",
]

SUMMARY_TABLE_TERMS = [
    "报告期内股本变化",
    "报告期内股权变动",
    "历次股本变化",
    "历次股权变动",
    "股本变化情况",
    "股权变动情况",
]

SECTION_TERMS = [
    "发行人基本情况",
    "发行人股本",
    "股本形成",
    "股本演变",
    "历史沿革",
    "设立以来",
    "主要股东",
    "控股股东",
    "实际控制人",
    "重大资产重组",
]


def read_universe():
    with UNIVERSE.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_document(row):
    names = [
        x.strip()
        for x in row["canonical_markdown_files"].split("|")
        if x.strip()
    ]

    parts = []
    missing = []

    for name in names:
        path = ROOT / "week1" / "review" / name

        if not path.exists():
            missing.append(name)
            continue

        parts.append(path.read_text(encoding="utf-8"))

    return "\n\n".join(parts), names, missing


def count_terms(text, terms):
    return {
        term: text.lower().count(term.lower())
        for term in terms
    }


def markdown_headings(lines):
    return [
        line.strip()
        for line in lines
        if re.match(r"^\s{0,3}#{1,6}\s+\S", line)
    ]


def html_table_count(text):
    return len(
        re.findall(
            r"<table\b",
            text,
            flags=re.I,
        )
    )


def markdown_table_lines(lines):
    out = []

    for line in lines:
        s = line.strip()

        if (
            s.count("|") >= 2
            and len(s) >= 5
        ):
            out.append(s)

    return out


def date_count(text):
    patterns = [
        r"(?:19|20)\d{2}\s*年\s*\d{1,2}\s*月(?:\s*\d{1,2}\s*日)?",
        r"(?:19|20)\d{2}[-/.]\d{1,2}(?:[-/.]\d{1,2})?",
    ]

    return sum(
        len(re.findall(p, text))
        for p in patterns
    )


def numbered_heading_count(lines):
    patterns = [
        r"^\s*[一二三四五六七八九十]+[、.]",
        r"^\s*[（(]\d+[）)]",
        r"^\s*\d+[、.]",
        r"^\s*\d+\.\d+",
    ]

    return sum(
        1
        for line in lines
        if any(re.search(p, line) for p in patterns)
    )


def longest_delimited_line(lines):
    """
    Detect lines likely to contain long subscriber/shareholder lists.
    This is a structure signal, not investor extraction.
    """
    best = 0
    best_line = ""

    for line in lines:
        s = line.strip()

        if len(s) > 1500:
            continue

        delimiters = len(
            re.findall(r"[、，,；;]", s)
        )

        if delimiters > best:
            best = delimiters
            best_line = s

    return best, best_line[:500]


def detect_equity_headings(headings):
    return [
        h
        for h in headings
        if any(term in h for term in EQUITY_TERMS)
    ]


def profile(row):
    text, parts, missing = load_document(row)
    lines = text.splitlines()

    headings = markdown_headings(lines)
    equity_headings = detect_equity_headings(headings)

    html_tables = html_table_count(text)
    md_table_rows = markdown_table_lines(lines)

    mermaid_count = len(
        re.findall(
            r"```mermaid",
            text,
            flags=re.I,
        )
    )

    image_count = len(
        re.findall(
            r"!\[[^\]]*\]\([^)]+\)",
            text,
        )
    )

    page_marker_count = len(
        re.findall(
            r"##\s*第\s*\d+\s*页",
            text,
        )
    )

    longest_list_delimiters, longest_list_example = (
        longest_delimited_line(lines)
    )

    equity_counts = count_terms(text, EQUITY_TERMS)
    restructuring_counts = count_terms(
        text,
        RESTRUCTURING_TERMS,
    )
    investor_counts = count_terms(text, INVESTOR_TERMS)
    vie_counts = count_terms(text, VIE_TERMS)
    summary_counts = count_terms(
        text,
        SUMMARY_TABLE_TERMS,
    )

    nonempty_lines = [
        x for x in lines if x.strip()
    ]

    table_line_count = len(md_table_rows)

    narrative_line_count = sum(
        1
        for line in nonempty_lines
        if "|" not in line
        and not line.lstrip().startswith("<")
    )

    character_count = len(text)

    result = {
        "document_id": row["document_id"],
        "stock_code": row["stock_code"],
        "company_short_name": row["company_short_name"],
        "board": row["board"],
        "historical_role": row["historical_role"],

        "canonical_parts": len(parts),
        "missing_parts": len(missing),

        "character_count": character_count,
        "line_count": len(lines),
        "nonempty_line_count": len(nonempty_lines),

        "markdown_heading_count": len(headings),
        "numbered_heading_count": numbered_heading_count(lines),
        "equity_heading_count": len(equity_headings),

        "html_table_count": html_tables,
        "markdown_table_line_count": table_line_count,
        "mermaid_count": mermaid_count,
        "image_count": image_count,
        "page_marker_count": page_marker_count,

        "date_expression_count": date_count(text),

        "equity_term_total": sum(equity_counts.values()),
        "restructuring_term_total": sum(
            restructuring_counts.values()
        ),
        "investor_term_total": sum(
            investor_counts.values()
        ),
        "vie_term_total": sum(vie_counts.values()),
        "summary_table_term_total": sum(
            summary_counts.values()
        ),

        "longest_delimited_line_score":
            longest_list_delimiters,

        "table_line_ratio":
            round(
                table_line_count
                / max(1, len(nonempty_lines)),
                6,
            ),

        "heading_density_per_10k_chars":
            round(
                len(headings)
                / max(1, character_count)
                * 10000,
                6,
            ),

        "equity_signal_per_10k_chars":
            round(
                sum(equity_counts.values())
                / max(1, character_count)
                * 10000,
                6,
            ),

        "investor_signal_per_10k_chars":
            round(
                sum(investor_counts.values())
                / max(1, character_count)
                * 10000,
                6,
            ),

        "narrative_line_ratio":
            round(
                narrative_line_count
                / max(1, len(nonempty_lines)),
                6,
            ),
    }

    detail = {
        "document": result,
        "canonical_files": parts,
        "missing_files": missing,
        "equity_headings": equity_headings[:100],
        "longest_delimited_line_example":
            longest_list_example,
        "term_counts": {
            "equity": equity_counts,
            "restructuring": restructuring_counts,
            "investor": investor_counts,
            "vie": vie_counts,
            "summary_table": summary_counts,
        },
    }

    return result, detail


def main():
    rows = read_universe()

    features = []

    print()
    print("===== PROFILING =====")

    for row in rows:
        result, detail = profile(row)
        features.append(result)

        out_json = (
            FEATURE_DIR
            / f"{row['document_id']}_{row['stock_code']}.json"
        )

        out_json.write_text(
            json.dumps(
                detail,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        print(
            row["stock_code"],
            row["company_short_name"],
            f"chars={result['character_count']}",
            f"headings={result['markdown_heading_count']}",
            f"tables={result['html_table_count']}",
            f"md_table_lines={result['markdown_table_line_count']}",
            f"mermaid={result['mermaid_count']}",
            f"long_list={result['longest_delimited_line_score']}",
        )

    fields = list(features[0].keys())

    with OUT_CSV.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(features)

    print()
    print("===== SUMMARY =====")
    print("Documents:", len(features))
    print(
        "Missing canonical parts:",
        sum(x["missing_parts"] for x in features),
    )

    numeric_summary = [
        "character_count",
        "markdown_heading_count",
        "html_table_count",
        "markdown_table_line_count",
        "mermaid_count",
        "equity_term_total",
        "restructuring_term_total",
        "investor_term_total",
        "longest_delimited_line_score",
    ]

    for key in numeric_summary:
        vals = [float(x[key]) for x in features]

        print(
            f"{key}: "
            f"min={min(vals):.2f} "
            f"mean={mean(vals):.2f} "
            f"max={max(vals):.2f}"
        )

    print()
    print(
        "Output:",
        OUT_CSV.relative_to(ROOT),
    )


if __name__ == "__main__":
    main()
