# Week 10 Stage 1C — Stratified Expansion Protocol

## Purpose

Expand the current prospectus seed without selecting companies according to
PE/VC richness or extractor performance.

## Core stratification

Board × IPO year:

- Main: 2022–2025, two new companies per year
- ChiNext: 2022–2025, two new companies per year
- BSE: 2022–2025, two new companies per year

Target new core samples: 24.

STAR is not expanded in this round because it is already overrepresented in
the existing seed.

## Selection rule

Candidate companies must be identified independently of PE/VC extraction
results.

Random seed:

`202610`

The seed and quota are frozen before candidate-pool completion.

## Eligibility

A company is eligible when:

1. it completed an IPO/listing in the specified board/year;
2. an official prospectus can be located;
3. it is not already present in the Week 10 seed;
4. the prospectus can be converted to a usable canonical text source.

## Important distinction

Core stratified samples are separate from later special/stress cases.

Complex VIE, red-chip, restructuring, table-heavy, or long-syndicate cases
must not replace randomly selected core samples.

## Outputs

- expansion_quota_v1.csv
- candidate_pool_v1.csv
- selected_expansion_v1.csv
- select_stratified_sample.py
