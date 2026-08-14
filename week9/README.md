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

Re-running the frozen parser today, with the reconstructed runtime (`markdown_source.py` = current `week6/pipeline/markdown_source.py`), reproduces **F1 89.66%** (Gold 42 / Auto 45 / TP 39 / FP 6 / FN 3):

```text
Precision  : 86.67%
Recall     : 92.86%
F1         : 89.66%
```

One-click reproduction:

```bash
python3 week9/reproduce_freeze.py
```

The ~4-point gap vs the original 94.12% is concentrated in four alias/normalization misses (e.g. `上汽科技` ↔ `SAIC TECHNOLOGIES FUND II`, `深圳达晨创程` ↔ `深圳市达晨创程…`) plus two parse artifacts — not a substantive pipeline difference.

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

## Week 10 Boundary

Week 10 begins with **Post-Blind Revision**. The original Blind Run #1 is never overwritten.

Priority revisions:

1. parse report-period equity-change summary tables;
2. expand long comma-separated institutional subscriber lists;
3. support group-level aggregate amounts/shares while preserving per-investor identity rows;
4. add explicit Pre-IPO syndicate expansion;
5. rerun as `Blind Run #2`, clearly separated from the original frozen result.
