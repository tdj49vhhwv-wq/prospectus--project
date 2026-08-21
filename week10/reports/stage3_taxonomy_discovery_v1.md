# Week 10 Stage 3 — Taxonomy Discovery v1

## Objective

Test whether prospectus structural features show stable grouping before
assigning semantic document types.

## Inputs

`week10/taxonomy/structure_features_v1.csv`

## Excluded from clustering

The clustering model does not use:

- company name;
- stock code;
- exchange or board;
- historical Dev/Blind role;
- Gold labels;
- PE/VC extraction results;
- Precision / Recall / F1.

## Method

Structural features are normalized by document length where appropriate.

Heavy list-length signals use `log1p`.

Features are standardized before clustering.

KMeans models for k=2 through k=6 are compared using silhouette score.

The best-k model is exploratory only.

Cluster numbers are not yet treated as semantic prospectus types.

## Next stage

Cluster membership and cluster feature profiles must be manually interpreted.

Only recurring structural patterns that can be described independently of
individual company names should become taxonomy categories.
