# Week 10 Stage 5B.4 — Official Resolver Progress

## Current state

The acquisition resolver remains fail-closed. The smoke-test manifest contains:

- 603312 西典新能 — SSE — target disclosure date 2024-01-08
- 301536 星宸科技 — SZSE — target disclosure date 2024-03-22
- 920002 万达轴承 — BSE — target disclosure date 2024-05-17

## Verified official discovery

### SSE / 603312 西典新能

An official SSE-hosted PDF was found and its parsed content identifies `苏州西典新能源电气股份有限公司 招股说明书（申报稿）`. This is added to `resolver_candidates_stage5b4_v1.csv` as a verified official-domain candidate. It is intentionally marked as the 2023 application draft rather than silently treated as the final 2024 issuance prospectus.

### SZSE / 301536 星宸科技

Official SZSE issuance materials confirm that the final `招股说明书` was scheduled for online disclosure on 2024-03-22. The exact final prospectus PDF URL has not yet been resolved, so no candidate is emitted. Fail-closed behavior is preserved.

### BSE / 920002 万达轴承

Official BSE later-period disclosure explicitly references the company's `招股说明书` disclosed on 2024-05-17. Search also finds official BSE prospectus-stage documents from 2023/2024, but the exact 2024-05-17 final prospectus URL has not yet been resolved. No final candidate is emitted until exact identity is verified.

## Next implementation step

Implement exchange-specific discovery adapters instead of relying on generic web discovery:

1. SSE: query official disclosure/project endpoints and select issuer + prospectus + target-stage document.
2. SZSE: query official IPO/finalpage disclosure endpoint around the target disclosure date and validate issuer/title.
3. BSE: query official disclosure/audit endpoint around 2024-05-17 and validate issuer/title.
4. Feed candidates into `resolve_official_sources_v1.py`.
5. Only after resolver acceptance: download bytes, require `%PDF-`, validate issuer/prospectus text, compute SHA256, and update manifest.

No third-party mirror is canonical, and unresolved cases remain unresolved.
