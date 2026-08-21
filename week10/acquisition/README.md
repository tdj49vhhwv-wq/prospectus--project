# Week 10 Acquisition

## Stage 5B.4 — Official Source Resolver v1

The acquisition layer is fail-closed. A search result is **not** automatically a source URL.

### Smoke-test issuers

| Code | Company | Exchange | Disclosure date | Initial state |
|---|---|---|---|---|
| 603312 | 西典新能 | SSE | 2024-01-08 | needs_resolution |
| 301536 | 星宸科技 | SZSE | 2024-03-22 | needs_resolution |
| 920002 | 万达轴承 | BSE | 2024-05-17 | needs_resolution |

### Resolver contract

Input candidate schema:

```csv
stock_code,url,title,source
603312,https://...,苏州西典新能源电气股份有限公司首次公开发行股票并在主板上市招股说明书,exchange_adapter
```

Run:

```bash
python3 week10/acquisition/resolve_official_sources_v1.py \
  --candidates week10/acquisition/resolver_candidates_v1.csv
```

Outputs:

- `week10/acquisition/resolver_v1/candidate_diagnostics_v1.csv`
- `week10/acquisition/resolver_v1/acquisition_manifest_resolved_v1.csv`

### Acceptance policy

Automatic acceptance requires:

1. URL host belongs to the expected exchange (`sse.com.cn`, `szse.cn`, or `bse.cn` and subdomains).
2. Candidate metadata matches the issuer name.
3. Candidate metadata identifies an 招股说明书.
4. Candidate is not a summary, listing announcement, pricing/result announcement, roadshow, etc.

Anything else remains `needs_resolution` and is not passed to the downloader.

### Why this is conservative

Search engines and finance portals can locate the correct document but are not treated as provenance for the research corpus. They may be used as discovery evidence while the resolver continues searching for the exchange-hosted disclosure object.

### Next adapter work

Implement exchange-specific discovery adapters for SSE, SZSE, and BSE, emit the common candidate schema above, then run this validator. Once the 3-company smoke test resolves and downloads correctly, run the same pipeline over the full 24-company Stage 5 manifest.
