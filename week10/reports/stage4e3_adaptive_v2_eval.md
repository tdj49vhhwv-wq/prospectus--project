# Week 10 Stage 4E.3 — Adaptive v2 Blind Evaluation

## Adaptive v1

Modules:

- summary-table detection
- row-aware equity-event parser
- long investor list extraction inside summary rows

Primary recovered structural case:

- 沐曦股份

## Adaptive v2 additional module

Narrative long-syndicate alias resolution.

Pattern:

member list → collective alias → aggregate investment action.

Primary recovered structural case:

- 摩尔线程 Pre-IPO syndicate

## Evaluation discipline

The original Week 9 blind Gold and exact matching key are reused.

No relaxed matching is introduced.

Historical blind failures were excluded from routing-threshold calibration.

## Ablation structure

Frozen baseline

→ Adaptive v1: summary-table path

→ Adaptive v2: summary-table + narrative long-syndicate paths

This permits attribution of performance gains to individual structural
modules.
