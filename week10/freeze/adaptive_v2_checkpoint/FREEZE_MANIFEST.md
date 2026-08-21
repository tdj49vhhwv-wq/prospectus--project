# Week 10 Adaptive v2 Checkpoint

## Purpose

Freeze the post-blind adaptive architecture before development
continues on new independent prospectuses.

## Historical blind documents

- 688795 摩尔线程
- 688802 沐曦股份

These documents must not be treated as a new untouched blind set.

## Frozen blind baseline

TP: 7
FP: 0
FN: 154
Precision: 100.00%
Recall: 4.35%
F1: 8.33%

## Adaptive v1

Structural addition:

- summary-table / row-aware parsing

Result:

TP: 32
FP: 0
FN: 129
Precision: 100.00%
Recall: 19.88%
F1: 33.16%

## Adaptive v2

Structural addition:

- narrative long-syndicate alias resolution

Result:

TP: 41
FP: 0
FN: 120
Precision: 100.00%
Recall: 25.47%
F1: 40.59%

## 688795 representation diagnosis

The long-syndicate parser successfully extracted:

- declared members: 38
- parsed members: 38
- date: 2024-12
- aggregate amount: 522452.9091
- aggregate shares: 7002.8217

The frozen institutional filter accepted only 9/38.

This is treated as a separate entity-classification issue,
not an extraction failure.

## Experimental rule

No further PE/VC classifier rules should be calibrated from
688795 or 688802.

Future classifier development must use independent documents.

A new untouched blind set must be created for final
generalization evaluation.
