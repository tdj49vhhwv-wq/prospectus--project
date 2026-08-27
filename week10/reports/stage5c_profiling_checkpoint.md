# Week 10 Stage 5C — Canonicalization + Independent Structure Profiling (checkpoint)

## Result

DEV 12 (Main 4 / ChiNext 4 / BSE 4, **zero STAR**) fully converted, profiled, and
routed against the frozen v1 thresholds. The router **partially generalizes**:

- **Structural dimensions generalize.** `long_list_log` fires `long_syndicate_parser`
  for **12/12** DEV docs (values 3.76–4.23, all above the v1 P75 = 2.56).
- **Vocabulary dimensions do NOT generalize.** `investor_signal` and `date_density`
  are **below the original-25 minimum for all 12 DEV docs**; `equity_signal`,
  `restructuring_signal`, and `vie_signal` never reach their P75. Consequently the
  specialized parsers `dense_equity_history_parser`, `restructuring_parser`,
  `vie_parser`, and `date_anchor_enhancer` fire for **0/12** DEV docs.

## Canonicalization

- 12/12 DEV prospectus PDFs converted to Markdown with MinerU 3.3.1
  (`-b pipeline -m txt -l ch`), sequential, offline-model mode.
- Conversion quality check: **12/12 OK, 0 flagged** (chars 668k–1.77M, headings
  744–1063, `<table>` blocks 248–447, date expressions 791–3805).
- Format caveat: MinerU 3.3.1 emits `#`/`##` headings + HTML tables and **no
  `## 第N页` page markers**, unlike the original 25's magic-pdf `*_正式稿_*.md`.
  `page_marker_count` is therefore 0 for all DEV docs. The 7 routing signals are
  text-content-based and remain comparable; only `page_marker_count` is affected.

## Signal distribution: DEV 12 vs original 25

| signal | orig min | orig P75 | #DEV < orig min | #DEV ≥ orig P75 |
|---|---|---|---|---|
| equity_signal | 0.82 | 2.84 | 4 (all 4 BSE) | **0** |
| investor_signal | 10.53 | 25.70 | **12** | **0** |
| restructuring_signal | 0.13 | 0.89 | 1 | 0 |
| summary_table_signal | 0.00 | 0.02 | 0 | 3 |
| vie_signal | 0.00 | 0.15 | 0 | 0 |
| date_density | 23.76 | 34.88 | **12** | **0** |
| long_list_log | 2.20 | 2.56 | 0 | **12** |

## Router application (frozen v1 thresholds)

All 12 route to `base_event_parser | long_syndicate_parser`; 3 also fire
`summary_table_parser` (001400, 301358, 603312). No other parser activates.

| board | n | special parsers (mean) | flags |
|---|---|---|---|
| Main | 4 | 1.50 | long_list ×4, summary_table ×2 |
| ChiNext | 4 | 1.25 | long_list ×4, summary_table ×1 |
| BSE | 4 | 1.00 | long_list ×4 |

## Why the vocabulary signals fail

The v1 thresholds were calibrated on a STAR-heavy seed (19/25 are 688xxx). STAR
prospectuses contain dense PE/VC fundraising sections (投资/基金/创投/认购/认缴)
and date-anchored equity-history tables (历次增资 dates). Main/ChiNext/BSE issuers —
especially BSE small-caps (920002 万达轴承 has 历史沿革=0, 基金=0, 创投=0) — use
different section vocabulary and simpler pre-IPO shareholder structures. The term-
and date-based signals therefore depress across the board, while the delimiter-
based `long_list_log` (shareholder/syndicate list structure) transfers cleanly.

This is the generalization gap the advisor asked about: the router is currently a
**STAR-board-tuned** system, not a cross-board one.

## Frozen artifacts

- Canonical text: `week10/canonical/<code>_<company>_招股说明书.md` (12 files, git-ignored)
- Quality check: `week10/canonical/quality_check_v1.csv`
- Features: `week10/profiler/structure_features_v2.csv`
- Signals: `week10/router/semantic_signals_v2.csv`
- Routes: `week10/router/router_application_v2.csv`
- Pipeline: `week10/canonical/code/convert_dev_pdfs.py` (sequential + retry),
  `week10/profiler/structure_profiler_v2.py`

## Next stage

Stage 5D — DEV extraction, then fix the router so its vocabulary signals stop
false-negativing cross-board issuers (board-agnostic term sets / board-normalized
thresholds / heavier weight on structural signals). VAL 6 only after the router is
re-frozen.
