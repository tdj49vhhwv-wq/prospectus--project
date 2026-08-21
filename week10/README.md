# Week 10 — Universal Prospectus PE/VC Extraction

## Research pivot

Week 10 changes the research target from a small fixed-company extractor to a general pipeline intended to process prospectuses across the market. The architecture is:

`prospectus universe -> structure profiler -> taxonomy/router -> adaptive parsers -> PE/VC extraction -> blind evaluation`

## Completed stages

### Stage 1 — Universe and coverage
- Seed universe: 25 prospectuses.
- Canonical source inventory completed; missing canonical parts = 0.
- Initial sample was STAR-heavy, motivating board-balanced expansion.
- Independent Stage 5 sample fixed at 24 companies: Main 8 / ChiNext 8 / BSE 8; DEV 12 / VAL 6 / BLIND 6.

### Stage 2 — Structure Profiler v1
Generated structural features for all 25 seed documents, including heading/table density, equity/restructuring/investor signals, VIE signals, date density, and long-list complexity.

### Stage 3 — Taxonomy and routing
Unsupervised clustering showed that naive clustering is dominated by formatting/structural outliers. The design therefore moved to interpretable structural dimensions and percentile-calibrated routing rather than treating KMeans labels as document types.

Adaptive routes include:
- `base_event_parser`
- `long_syndicate_parser`
- `date_anchor_enhancer`
- `summary_table_parser`
- `vie_parser`
- `dense_equity_history_parser`
- `restructuring_parser`

Threshold calibration excludes the two historical blind failures.

### Stage 4 — Adaptive extraction
Summary-block detection was upgraded from literal table detection to block-level detection. Row-aware parsing was then added for table-like prospectus sections.

For 688802 沐曦股份, the row-aware parser recovered long investor lists, including 63 investors in the 2025-03 financing row.

For 688795 摩尔线程, the long-syndicate parser recovered the declared 38-member Pre-IPO investor group. The frozen PE/VC classifier accepted 9 of those 38 as institutional PE/VC rows.

#### Blind evaluation checkpoint

| Version | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| Frozen | 7 | 0 | 154 | 100.00% | 4.35% | 8.33% |
| Adaptive v1 | 32 | 0 | 129 | 100.00% | 19.88% | 33.16% |
| Adaptive v2 | 41 | 0 | 120 | 100.00% | 25.47% | 40.59% |

Adaptive v2 was frozen under `week10/freeze/adaptive_v2_checkpoint/` in the local research workspace before Stage 5 acquisition work.

## Stage 5 — Independent board-balanced acquisition

### Sampling manifest
24 independent samples:
- Main: 8 (DEV 4 / VAL 2 / BLIND 2)
- ChiNext: 8 (DEV 4 / VAL 2 / BLIND 2)
- BSE: 8 (DEV 4 / VAL 2 / BLIND 2)
- Years: 2023 = 7, 2024 = 11, 2025 = 6

### Stage 5B smoke-test acquisition set
- 603312 西典新能 — SSE Main — 2024-01-08
- 301536 星宸科技 — SZSE ChiNext — 2024-03-22
- 920002 万达轴承 — BSE — 2024-05-17

The first resolver attempt left all three records as `needs_resolution`; source URLs were empty. Stage 5B.4 therefore introduces an explicit resolver architecture rather than silently accepting search-engine URLs.

## Stage 5B.4 design

`resolve_official_sources_v1.py` separates discovery from validation:

1. Exchange-specific candidate discovery.
2. Candidate normalization.
3. Strict issuer/code/document-title checks.
4. Preference for official exchange/issuer disclosure hosts.
5. Status values that distinguish `resolved_official`, `candidate_needs_validation`, and `unresolved`.
6. No download is permitted from an unresolved candidate.

This is deliberately conservative: acquisition should fail closed rather than pollute the research corpus with a wrong prospectus.

## Next

Run the Stage 5B.4 smoke test on the three issuers, inspect diagnostics, then connect only validated URLs to the PDF downloader / `%PDF` check / SHA256 stage. After the three-exchange smoke test passes, expand the resolver to all 24 independent samples.
