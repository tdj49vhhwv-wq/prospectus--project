# Week 10 Stage 2 — Prospectus Structure Profiler v1

## Goal

Measure prospectus structure before defining taxonomy or changing PE/VC
extraction rules.

## Design constraint

The profiler does not read Gold labels and does not use extractor accuracy.

## Feature families

1. document size and segmentation;
2. Markdown and numbered heading structure;
3. HTML/Markdown tables;
4. Mermaid/diagram presence;
5. equity-history structural signals;
6. restructuring/VIE signals;
7. date-expression density;
8. long delimited-list signals;
9. table versus narrative density.

## Important

These features are descriptive signals only.

No prospectus type is assigned in Stage 2.

Taxonomy labels will be considered only after feature inspection and
clustering in Stage 3.
