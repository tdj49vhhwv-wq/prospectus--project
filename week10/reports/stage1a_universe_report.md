# Week 10 Stage 1A — Canonical Universe Seed

## Objective

Build one canonical research document per company before structural profiling.

A canonical document may consist of multiple Markdown parts.

## Source of truth

The historical Markdown mapping is inherited from:

`week6/pipeline/markdown_source.py`

This preserves the exact input structure used by the Week 8/9 pipeline.

## Roles

- `historical_dev`: original 8-company development sample
- `historical_blind_failure`: Week 9 blind-test failure cases
- `exploratory`: additional prospectuses available in the repository

## Rules

1. One stock code corresponds to one research document.
2. Multiple Markdown parts belonging to the same prospectus are not treated as separate samples.
3. All required canonical parts must exist before profiling.
4. Structure type is intentionally blank at Stage 1A.
5. Taxonomy will be inferred only after structural profiling.

## Next step

Stage 1B will measure board/year/sample imbalance and define the external expansion quota.

Stage 2 will implement Prospectus Structure Profiler v1.
