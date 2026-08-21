# Week 10 Stage 4C — Long Syndicate / Investor Normalization

## Input

Row-level equity events from Stage 4B.2.

## Goal

Extract every disclosed investor group within each financing row and normalize
investor names.

## Key distinction

Stage 4C does not modify event boundaries.

Event identification and investor extraction are separated deliberately.

## Normalization

PDF line-wrap artifacts inside investor names are repaired before splitting.

Examples:

- 嘉 兴普超 → 嘉兴普超
- 经纬 厦门 → 经纬厦门
- 新华 文泰 → 新华文泰

## Next

Stage 4D will:

1. classify normalized names as institutional / non-institutional candidates;
2. merge adaptive rows with the frozen baseline;
3. deduplicate overlapping events/investors;
4. rerun evaluation.
