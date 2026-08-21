# Week 10 Stage 4D — Adaptive Blind Evaluation v1

## Baseline

Week 9 Formal Blind Run #1.

## Adaptive v1 modules

- representation-agnostic summary detection
- row-aware equity-event parsing
- long-syndicate investor extraction
- frozen Stage 7.1 institution classification

## Evaluation

The exact Week 9 Blind Run #1 key is reused:

stock code + subscription month + event context + normalized subscriber name.

No relaxed matching is introduced for Week 10.

## Important limitation

Adaptive v1 currently implements the summary-table / long-syndicate path most
fully for documents routed through the summary-table branch.

Results should therefore be interpreted as an incremental module evaluation,
not yet as the final generalized system result.
