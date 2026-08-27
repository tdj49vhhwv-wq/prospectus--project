# Week 10 Stage 5D — Cross-board Extractor Freeze (pre-BLIND)

## Purpose

Freeze the generalized cross-board (Main / ChiNext / BSE) PE/VC extractor
and its evaluation harness **before** the BLIND 6 one-shot run.  No BLIND 6
PE/VC content has been read or extracted at this point.

## Frozen artifacts

- Extractor: `code/extract_cross_board.py` (imports frozen Stage 7.2
  `week9/stage72_postblind` for `markdown_source` + `event_local_pevc.alias_map`)
- Eval harness: `eval/evaluate_stage5d.py`
- Gold (DEV): `eval/dev12_gold_draft.csv` (61 PE/VC rows)
- Gold (VAL): `eval/val6_gold_draft.csv` (16 PE/VC rows)

## Frozen results (MinerU 3.3.1 canonical markdown, `PROSPECTUS_MD_DIR=week10/canonical`)

### VAL 6 (final tuning target)

- TP 16 / FP 0 / FN 0 — **Precision 100% · Recall 100% · F1 100%**
- per-company: 001306=0, 603310=6, 301550=4, 301606=5, 920703=1, 920019=0

### DEV 12 (hold-out diagnostic)

- TP 57 / FP 20 / FN 4 — Precision 74.03% · Recall 93.44% · **F1 82.61%**
  (baseline before VAL-driven fixes was F1 79.19% / TP 59 / FP 29 / FN 2)

## Extractor changes this stage (vs frozen Stage 7.2 parser)

1. `is_institution`: fund/batch-number suffix (`麦岛6号`, `一期`…) precedes digit
   rejection.
2. `heading_event` 设立 broaden → `有限公司设立 | 首期出资 | 设立及`.
3. New exclusion sets, all fed through `add()`:
   - `controllers()` — 控股股东/实际控制人 + 其控制的企业 + 发行人自身
     全资/控股/参股子公司/分公司 + 同受控制的关联方 (header-aware table scan
     + `_full2alias` reverse glossary incl. 曾用名 segments).
   - `issuer_names()` — 发行人别名 + 前身实体.
   - `holding_spvs()` — 企业管理/管理咨询型合伙 SPV.
   - `employee_platforms()` / `tech_founders()` (retained from Stage 7.2).
4. New extraction paths (needed for Main/ChiNext/BSE disclosure styles):
   - `extract_recent_new_shareholders()` — 新增股东情况 (table + subsection).
   - `extract_heading_investors()` — 引入/引进 X、Y… in headings.
   - `extract_subscriber_names()` — 增资股东/发行对象/认购人 tables.
5. `prose_date_ym` prefers 股东大会/发行/增资/验资 dates over 董事会.

## Known residual error (documented, not fixed pre-freeze)

- **DEV FN (4):** 深圳昆宸 (企业管理咨询 SPV 但实为机构 PE — `holding_spvs`
  over-fires), 东莞博英 / 赣州博怀 (gold 标注自注「疑似员工/创始人平台，待确认」),
  四川省国投 (入股时点未披露，仅现身前十名股东).
- **DEV FP (20):** 国有控股股东体系内实体 (陕西电投/安康发展/岚皋/湘潭天易 —
  「国有控股股东内部重组」口径), 301536 整体变更发起人 (MELSTONE/FRANKSTONE/
  创熠芯跑一号/厦门联和/芯跑共赢 — 员工平台 vs PE 边界，gold 自注待确认),
  广西裕宁原股东以股权认缴的资产注入方 (津晟新材料/南宁楚达), 前身/合并片段
  噪音 (华秦投资享有/商洛发电、正元实业 等).
- These reflect real cross-board generalization friction (国有 restructuring +
  SPV-vs-fund + ESOP-vs-PE), not extraction-structure failures.

## Next stage

BLIND 6 (603257 / 603210 / 301629 / 301658 / 920060 / 920098) — convert PDF →
canonical markdown, then one-shot run of this frozen extractor.  No code changes.
