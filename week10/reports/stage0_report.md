# Week 10 Stage 0 Report

## Research transition

Week 1–9 focused primarily on a small development set of IPO prospectuses.

Week 10 changes the research objective from company-specific PE/VC
extraction to a generalized prospectus extraction framework.

## Frozen baseline

Baseline implementation:

`week9/stage71_frozen/`

This version must remain immutable.

## Week 10 research pipeline

Prospectus Universe

→ Structure Profiler

→ Prospectus Taxonomy

→ Type Classification

→ Type-aware PE/VC Extraction

→ Blind Generalization Evaluation

## Stage 0 outputs

- `week10/universe/prospectus_universe_v0.csv`
- `week10/baseline/`
- `week10/reports/stage0_report.md`

## Next stage

Week 10 Stage 1:

Prospectus Structure Profiler v1

The profiler will extract structural features from prospectus Markdown
without attempting PE/VC event extraction.
