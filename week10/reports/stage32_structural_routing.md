# Week 10 Stage 3.2 — Structural Routing Schema v1

## Finding from Stage 3/3.1

Discrete clustering does not currently provide a defensible prospectus
taxonomy.

The best semantic clustering separates one restructuring outlier from the
remaining documents.

Therefore the project adopts a multi-dimensional structural representation.

## Structural dimensions

- equity complexity
- investor complexity
- restructuring complexity
- summary-table complexity
- VIE complexity
- date complexity
- long-list complexity

## Threshold calibration

Thresholds use P75 and P90.

Historical Blind Run #1 companies are excluded from threshold calibration.

This prevents post-blind leakage.

## Interpretation

- NORMAL: below P75
- HIGH: P75–P90
- EXTREME: >= P90

## Routing

Every prospectus receives the base parser.

Additional parsers are activated by structural signals:

- summary-table → summary_table_parser
- investor / long-list → long_syndicate_parser
- restructuring → restructuring_parser
- VIE → vie_parser
- dense equity history → dense_equity_history_parser
- high date complexity → date_anchor_enhancer

## Research implication

The proposed system is not a company-specific rule set.

It is a structure-adaptive extraction framework in which parser selection is
determined by document characteristics.
