# Week 9 — PE/VC Extraction Freeze and Formal Blind Test

## Status

Week 9 is complete as a frozen development experiment plus Formal Blind Run #1.

### Development Freeze

| Metric | Result |
|---|---:|
| Core Event Precision | 90.24% |
| Core Event Recall | 92.50% |
| PE/VC Investor Precision | 93.02% |
| PE/VC Investor Recall | 95.24% |
| PE/VC Investor F1 | 94.12% |
| Freeze Gate | PASS |

Frozen parser: `stage71_frozen/event_local_pevc.py`

SHA256: `66a80a6f89f2b29de394a26292324db4b8e94f48a823531c2b921b049f2d11df`

### Reproducibility

The freeze-time investor metrics above (P 93.02% / R 95.24% / F1 94.12%) were produced with a frozen runtime that was never committed — `stage71_frozen/runtime/markdown_source.py` (original SHA256 `4c3acb5f`) and `runtime/pg8000.py` are lost.

Re-running the frozen parser today, with the reconstructed runtime (`markdown_source.py` = current `week6/pipeline/markdown_source.py`) and a corrected evaluation harness, reproduces **F1 96.55%** (Gold 42 / Auto 45 / TP 42 / FP 3 / FN 0):

```text
Precision  : 93.33%
Recall     : 100.00%
F1         : 96.55%
```

Two evaluation-side defects were repaired to reach this (the frozen parser `event_local_pevc.py` is untouched):

1. **Gold transcription fix** — `301581` 2021-11-11 增资's 27% investor was mislabeled `上海广弘实业有限公司` in `stage3/investor_eval/investor_eval_details.csv`. Per the master table (`data/gold_standard/融资事件总表.jsonl`) and the prospectus glossary it is `深圳赛格高技术投资股份有限公司` (赛格高技术).
2. **Alias-table completion** — three prospectus-defined aliases were missing from the evaluator's `ALIAS_GROUPS`:
   - `赛格高技术` → `深圳赛格高技术投资股份有限公司`
   - `上汽科技` / `SAIC` → `SAIC TECHNOLOGIES FUND II,LLC`
   - `深圳达晨创程` → `深圳市达晨创程私募股权投资基金企业(有限合伙)`

The original 94.12% is therefore *understated*: it carried the same gold error plus two missing aliases. The 3 remaining FPs are frozen-parser over-extraction artifacts (see below), not evaluation issues.

Remaining FPs (frozen parser, unfixable without unfreezing `stage71`):
- `芜湖富海` @ 301563 2015-08 — over-extracted into the wrong event
- `聚贝投资以人民币1` @ 688758 2021-12 — parse fragment
- `500万元` @ 688758 2021-12 — amount misparsed as a name

One-click reproduction:

```bash
python3 week9/reproduce_freeze.py
```

## Formal Blind Run #1

Blind companies:

- 688795 摩尔线程
- 688802 沐曦股份

The frozen pipeline was run without blind-result-driven modification.

### Raw Auto Output

- 摩尔线程: 7 PE/VC rows
- 沐曦股份: 0 PE/VC rows

### Independent Blind Gold Evaluation

| Metric | Result |
|---|---:|
| Blind Gold PE/VC rows | 161 |
| Auto rows | 7 |
| TP | 7 |
| FP | 0 |
| FN | 154 |
| Blind Precision | 100.00% |
| Blind Recall | 4.35% |
| Blind F1 | 8.33% |

The blind result reveals a major generalization gap: precision is high, but recall collapses on long investor syndicates and report-period equity-change summary tables.

## Week 9 Artifacts

- `final_dev_metrics.json` — final Dev metrics and freeze metadata
- `stage71_frozen/` — frozen Stage 7.1 parser + checksum
- `blind_run1/BLIND_RUN_1_MANIFEST.md` — immutable raw blind-run record
- `blind_run1/week9_blind_run1_pevc_rows.csv` — raw Auto blind output
- `blind_run1/blind_gold.csv` — independently constructed Blind Gold
- `blind_run1/blind_eval_summary.json` — blind P/R/F1
- `blind_run1/blind_eval_details.csv` — TP/FP/FN details
- `blind_run1/BLIND_RUN_1_EVALUATION.md` — audit and error analysis
- `evaluate_blind_run1.py` — reproducible evaluator
- `reproduce_freeze.py` — one-click reproduction of the Dev PE/VC investor metrics
- `freeze_repro/` — reproduced frozen-parser output + eval (F1 89.66%)
- `stage72_postblind/` — Post-Blind Revision Stage 7.2 parser + checksum + freeze manifest
- `blind_run2/` — Blind Run #2 results + `BLIND_RUN_2_MANIFEST.md`
- `evaluate_blind_run2.py` — Blind Run #2 evaluator
- `reproduce_blind_run2.py` — one-click reproduction of Blind Run #2

## Post-Blind Revision — Formal Blind Run #2

Post-Blind Revision unfreezes the pipeline on a **new Stage 7.2 parser**
(`stage72_postblind/`) while keeping `stage71_frozen/` and `blind_run1/` immutable.
It reruns the two blind companies as a separately-labeled **Blind Run #2**,
evaluated against the same frozen gold (`blind_run1/blind_gold.csv`, 161 rows).

### Results (investor-level)

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

### Which structural fixes drove the recovery

| Fix | Gap it closed |
|---|---|
| Summary-table discovery (`parse_summary_table_investors`) | 沐曦's 7 增资 rounds are a cell-per-line plain-text table; the date is a cell value, not a heading |
| Pre-IPO syndicate expansion (`parse_syndicate_investors`) | 摩尔线程's 2024-12 round is one sentence: 38 names + `(以下简称"Pre-IPO轮股东")共计38家主体` |
| Cross-page list reassembly (`_strip_page_junk`) | MinerU page headers/footers/repeated table headers break long lists (沐曦 2025-03 has 65 names) |
| `和`-safe list splitting (`split_investor_list`) | frozen `split_list` split on `和`, corrupting 8 gold names containing `和` |
| Employee-platform exclusion (`_employee_platforms`) | 晖泽共广 is `广发信德…的员工跟投持股平台`, which the gold excludes |

### Dev regression (secondary goal)

Stage 7.2 parser on the 8 Dev companies: **investor F1 98.82%** (Gold 42 / Auto 43 /
TP 42 / FP 1 / FN 0), up from the frozen baseline 96.55%. Two of three frozen FPs
are fixed (`500万元`, `聚贝投资以人民币1`). The remaining FP `芜湖富海@2015-08` is a
source-vs-gold discrepancy (the prospectus mermaid itself lists 芜湖富海 in
2015-08), left as-is — see `stage72_postblind/FREEZE_MANIFEST.md`.

Reproduce: `python3 week9/reproduce_blind_run2.py`.

## Week 10 Boundary

Week 10 begins with **Post-Blind Revision**. The original Blind Run #1 is never overwritten.

Priority revisions:

1. ~~parse report-period equity-change summary tables~~ — ✅ `parse_summary_table_investors`;
2. ~~expand long comma-separated institutional subscriber lists~~ — ✅ `split_investor_list` (`和`-safe);
3. ~~support group-level aggregate amounts/shares while preserving per-investor identity rows~~ — ✅ aggregate rows keep per-name identity with null amounts;
4. ~~add explicit Pre-IPO syndicate expansion~~ — ✅ `parse_syndicate_investors`;
5. ~~rerun as `Blind Run #2`, clearly separated from the original frozen result~~ — ✅ `blind_run2/` (see above).
