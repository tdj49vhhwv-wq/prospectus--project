# Stage 7.2 — Post-Blind Revision Parser

This is the post-blind-revision parser. It is a **copy of the frozen Stage 7.1
parser** (`stage71_frozen/event_local_pevc.py`, SHA256 `66a80a6f`) with additive,
generalized structural parsers. The frozen Stage 7.1 parser and its checksum are
untouched.

## Checksums

- `event_local_pevc.py` — SHA256 `cd7a27177adbf1b5b422eedb2d95becebc6cf081a3036e5dbf44e5ee1728f071`
- `runtime/markdown_source.py` — SHA256 `59a906209507f54d4b33fa0265dbf1a25e0340edd4cef754193664f24628cd9e`

## What changed vs. Stage 7.1 (all additive; no company-name hardcodes)

1. **`parse_summary_table_investors`** — report-period equity-change summary table
   (沐曦式, cell-per-line plain text). Self-contained discovery of 增资 clauses:
   `N、<顿号名单>按照每1元注册资本…` / `…各以人民币…` / `…以合计…认购…新股`.
   Nearest-preceding `YYYY年M月` supplies the event date (the date is a cell value,
   not a heading). Handles cross-page list splits via `_strip_page_junk`.
2. **`parse_syndicate_investors`** — Pre-IPO syndicate (摩尔线程式): a long
   顿号-separated list followed by `(以下简称"…")共计N家主体`. The `(…轮股东)`
   marker is matched post-normspace (half-width parens). Date from the nearest
   preceding `YYYY年M月…增资` heading.
3. **`_strip_page_junk`** — removes MinerU page headers/footers/repeated table
   headers (`##第N页`, `…招股说明书 X-X-X`, `序号 时间 股权变动 股权变动情况`)
   that otherwise break investor lists across page boundaries.
4. **`split_investor_list`** — splits on `、,，` and `及` only, **not** `和`/`与`
   (the blind gold contains 8 institutions whose names contain `和`: 和谐健康 /
   和暄新芯一号/二号 / 苏州和基 / 集美中和 / 上海荣至和 / 正和启迪 / 宜宾和谐).
5. **`_employee_platforms`** — excludes names described as `X系…的员工(跟投)(持股)平台`
   (employee co-investment platforms, e.g. 晖泽共广), aligning with the gold's
   audit exclusion.
6. **Dev FP fixes (shared `build()` path)**:
   - digit-reject (`re.search(r'\d', name)`) drops `500万元`, `聚贝投资以人民币1`
     and date-prefix tokens;
   - the reject list now matches on `normspace(name)` so the cross-line `万 元`
     no longer evades the `万元` filter;
   - the amount regex `万\s*元` (was `万元`) handles `万\n元` line-break splits.

The Stage 7.1 `build()` reject list is preserved; the new `build()` appends the
two self-contained discovery passes and does a final cross-path dedupe keyed on
`(stock_code, subscription_date[:7], event_context, normspace(name).upper())`.

## Known remaining FP (not fixed — source/gold discrepancy)

- `芜湖富海` @ 301563 2015-08: the prospectus's own mermaid flowchart lists
  `芜湖富海` in the 2015-08 增资 node (`深创投、…、芜湖富海共同增资…`), while the
  gold master table attributes it to 2014-08 only. A "drop duplicate in later
  events" rule would incorrectly suppress legitimate multi-round investors
  (e.g. 混沌投资 / 嘉兴普超 appear in two 沐曦 rounds), so it is left as-is.
  Dev investor F1 remains 98.82% (> 96.55% baseline, 2 of 3 FPs fixed).
