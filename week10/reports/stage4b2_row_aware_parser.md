# Week 10 Stage 4B.2 — Row-aware Equity Summary Parser

## Diagnosis

Flattened prospectus tables preserve logical rows using:

row number → date → equity-change label → description.

Date-only splitting is insufficient because multiple distinct events may occur
in the same month.

## Strategy

Rows are identified by an isolated integer followed shortly by a transaction
date.

Each row ends at the next valid row number.

This prevents:

- amount leakage;
- investor-list leakage;
- mixed event classification across adjacent rows.

## Exclusion

Capital reserve proportional capitalization is excluded from PE/VC event
candidates.

## Next

Stage 4C will normalize and split investor names from each row-level investor
group.
