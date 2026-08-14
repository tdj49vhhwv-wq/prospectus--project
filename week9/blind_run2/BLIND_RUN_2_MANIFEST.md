# Week 9 Post-Blind Revision — Formal Blind Run #2

## What this is

Blind Run #2 is the Post-Blind Revision rerun on the same two blind companies
(688795 摩尔线程, 688802 沐曦股份), evaluated against the **frozen** Blind Run #1
gold (`week9/blind_run1/blind_gold.csv`, 161 rows, `include_pevc=是`).

The frozen Stage 7.1 parser (`stage71_frozen/`) and Blind Run #1 artifacts
(`blind_run1/`) are **immutable and untouched**. This run uses the Stage 7.2
parser (`stage72_postblind/`).

## Parser

- `stage72_postblind/event_local_pevc.py`
- SHA256: `cd7a27177adbf1b5b422eedb2d95becebc6cf081a3036e5dbf44e5ee1728f071`

## Results (investor-level, matching Blind Run #1's key)

| Metric | Blind Run #1 | Blind Run #2 |
|---|---:|---:|
| Gold PE/VC rows | 161 | 161 |
| Auto PE/VC rows | 7 | 161 |
| TP | 7 | 161 |
| FP | 0 | 0 |
| FN | 154 | 0 |
| Precision | 100.00% | 100.00% |
| Recall | 4.35% | 100.00% |
| F1 | 8.33% | 100.00% |

## Per-company breakdown

| Company | Month | Gold | Auto | Status |
|---|---:|---:|---|
| 摩尔线程 | 2022-12 增资及股权转让 | 4 | 4 | ✓ |
| 摩尔线程 | 2023-10 增资 | 5 | 5 | ✓ |
| 摩尔线程 | 2024-12 增资 (Pre-IPO syndicate) | 38 | 38 | ✓ |
| 沐曦股份 | 2022-09 / 2023-02 / 2023-04 | 10/7/1 | 10/7/1 | ✓ |
| 沐曦股份 | 2023-12 / 2024-08 | 8/7 | 8/7 | ✓ |
| 沐曦股份 | 2025-02 | 16 | 16 | ✓ (晖泽共广 excluded) |
| 沐曦股份 | 2025-03 | 65 | 65 | ✓ (cross-page list reassembled) |

## What structural fixes drove the recovery

1. **Summary-table discovery** (沐曦): the 7 增资 rounds are a cell-per-line
   plain-text table where the date is a cell value, not a heading. New
   `parse_summary_table_investors` finds `N、<顿号名单>按照每1元注册资本/以合计…认购`
   clauses and associates the nearest preceding `YYYY年M月`.
2. **Pre-IPO syndicate expansion** (摩尔线程): the 2024-12 round is a single
   sentence with 38 names + `(以下简称"Pre-IPO轮股东")共计38家主体`. New
   `parse_syndicate_investors` expands the full list.
3. **Cross-page list reassembly**: MinerU page headers/footers/repeated table
   headers break long lists (沐曦 2025-03 has 65 names spanning pages).
   `_strip_page_junk` removes them before matching.
4. **`和`-safe list splitting**: the frozen `split_list` split on `和`, corrupting
   8 gold institution names that contain `和` (和谐健康, 和暄新芯, 苏州和基, …).
   New `split_investor_list` splits only on `、,，及`.
5. **Employee-platform exclusion**: 晖泽共广 is `广发信德…的员工跟投持股平台`;
   `_employee_platforms` excludes it, matching the gold's audit exclusion.

## Artifacts

- `week9_blind_run2_pevc_rows.csv` — Stage 7.2 raw auto output (161 rows)
- `blind_eval_summary.json` — P/R/F1
- `blind_eval_details.csv` — 161 TP, 0 FP, 0 FN
- Reproduce: `python3 week9/reproduce_blind_run2.py`
- Evaluate only: `python3 week9/evaluate_blind_run2.py`

## Dev regression (secondary goal)

Stage 7.2 parser on the 8 Dev companies: **investor F1 98.82%** (Gold 42 / Auto 43 /
TP 42 / FP 1 / FN 0), up from the frozen baseline 96.55%. Two of three frozen
FPs are fixed (`500万元`, `聚贝投资以人民币1`). The remaining FP `芜湖富海@2015-08`
is a source-vs-gold discrepancy (the prospectus mermaid itself lists 芜湖富海 in
2015-08) — see `stage72_postblind/FREEZE_MANIFEST.md`.
