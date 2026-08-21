# Week 10 Stage 3.1 — Parser Bias Check

## Stage 3 finding

The initial all-feature clustering produced a 3-versus-22 split.

The three-document cluster consisted of:

- 三联锻造
- 云汉芯城
- 友升股份

These documents also showed unusually high table, Mermaid, heading and
delimited-list signals.

Many of these features were extremely correlated.

This pattern is consistent with parser / Markdown representation effects and
must not be interpreted directly as a prospectus taxonomy.

## Stage 3.1 correction

Parser-sensitive features are removed.

Semantic-only clustering uses:

- equity signal
- investor signal
- restructuring signal
- summary-table signal
- VIE signal
- date density
- long-list complexity

Robust scaling is used because several signals are heavy-tailed.

KMeans and hierarchical clustering are compared.

Leave-one-out stability is measured using Adjusted Rand Index.

## Interpretation rule

A discrete taxonomy will only be adopted if clusters are:

1. reasonably balanced;
2. stable to document removal;
3. supported across clustering methods;
4. semantically interpretable;
5. reproducible after the Stage 1C sample expansion.

Otherwise Week 10 will model prospectus structure as continuous dimensions
and route extraction strategies using structural signals rather than forcing
documents into artificial categories.
