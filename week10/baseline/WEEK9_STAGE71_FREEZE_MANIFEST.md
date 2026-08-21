# Week 9 Pipeline Freeze

Freeze gate (Dev 8):
- Core Event Precision: 90.24%
- Core Event Recall: 92.50%
- PE/VC-focused Investor: TP=40, FP=3, FN=2
- PE/VC Precision: 93.02%
- PE/VC Recall: 95.24%
- PE/VC F1: 94.12%
- Gate: PASS

Protocol:
- Event logic frozen from the stable Week 9 development pipeline.
- PE/VC investor parser uses event-local transaction blocks only.
- Formal headings override Mermaid evidence; Mermaid is fallback only when no formal event section exists.
- Investor identities require transaction structure (subscription/contribution/issuance), followed by institution/entity filtering.
- Prospectus-defined aliases are used for entity normalization.
- No blind-test result may be used to modify the frozen logic before Blind Run #1 is recorded.

## Runtime reconstruction (2026-08-14)

The original frozen `runtime/` directory was never committed. Of the four files
listed in the original SHA256SUMS.txt, only `event_local_pevc.py` survived.

- `runtime/markdown_source.py` — reconstructed from `week6/pipeline/markdown_source.py`
  (SHA256 `cfaec860`). The original frozen version (`4c3acb5f`) was never committed and is lost.
- `runtime/run_md_pipeline.py` — never committed; equivalent is `week6/pipeline/run_md_pipeline.py`
  (SHA256 `fb328d4f`, matches the original manifest entry).
- `runtime/pg8000.py` — never committed; unrecoverable (not in any branch or history).
  It is not imported by `event_local_pevc.py` or `markdown_source.py`, so it does not block reproduction.

Reproducing the freeze with the reconstructed runtime yields PE/VC investor
F1 89.66% (Gold 42 / Auto 45 / TP 39 / FP 6 / FN 3) when the committed
evaluation harness is used as-is, versus the original freeze claim of 94.12%
(TP 40 / FP 3 / FN 2).

## Evaluation-harness reconstruction (2026-08-14)

Two evaluation-side defects were found and repaired (the frozen parser
`event_local_pevc.py` is untouched):

1. Gold transcription error — `301581` 2021-11-11 增资's 27% investor was
   mislabeled `上海广弘实业有限公司` in `stage3/investor_eval/investor_eval_details.csv`;
   it is `深圳赛格高技术投资股份有限公司` (赛格高技术) per the master table and glossary.
2. Missing aliases in `stage7/evaluate_pevc_investors_v2_fixed.py` `ALIAS_GROUPS`:
   赛格高技术→深圳赛格高技术投资股份有限公司, 上汽科技/SAIC→SAIC TECHNOLOGIES FUND II LLC,
   深圳达晨创程→深圳市达晨创程私募股权投资基金企业(有限合伙).

With both repairs, the reproducible metric is PE/VC investor F1 96.55%
(Gold 42 / Auto 45 / TP 42 / FP 3 / FN 0), exceeding the original 94.12%.
The 3 remaining FPs (芜湖富海@2015-08, 聚贝投资以人民币1, 500万元) are frozen-parser
over-extraction artifacts. See `week9/reproduce_freeze.py`.
