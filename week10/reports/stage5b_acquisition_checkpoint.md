# Week 10 Stage 5B — Prospectus Acquisition Checkpoint

## Result

24 / 24 frozen independent-sample prospectuses `downloaded_validated`.

| Exchange | Count | Source |
|---|---|---|
| SSE | 5 | cninfo (巨潮资讯网, CSRC-designated official disclosure) |
| SZSE | 11 | cninfo |
| BSE | 8 | bse.cn (北交所) |

Every row carries a SHA256 digest that was re-verified against the on-disk
PDF after the final run. No silent replacement occurred.

## Acquisition adapters

Discovery is consolidated into exactly three exchange routes:

- `discovery/sse.py`  — cninfo `column=sse` (SSE `static.sse.com.cn` serves a
  JS anti-bot challenge; cninfo hosts the identical official PDF).
- `discovery/szse.py` — cninfo `column=szse`.
- `discovery/bse.py`  — bse.cn `zoneInfoResult.do` (BSE is not covered by
  cninfo; `disclosureTypes[]=9533` selects 招股说明书).

## Fail-closed gate chain

A row advances only when every gate passes; on failure it stops at a named
status and is never silently replaced:

```
discovery (official URL)
  -> HTTP 200
  -> %PDF magic bytes
  -> minimum file size (>= 500 KB)
  -> prospectus title  (招股说明书)
  -> issuer identity   (company name in text)
  -> stock code        (metadata / text)
  -> SHA256
  -> manifest status = downloaded_validated
```

Failure statuses: `discovery_failed`, `not_pdf`, `too_small`,
`identity_failed`, `code_mismatch`, `failed`.

## Fixes required during the 24-company batch

1. **BSE adapter broke after refactor** — `disclosureTypes[]=9533` was dropped,
   so bse.cn returned `请求参数异常` (KeyError `listInfo`). Restored the
   parameter.
2. **cninfo search key** — searching `公司简称 招股说明书` missed issuers whose
   prospectus title uses the full registered name (e.g. 斯菱股份). Switched to
   `股票代码 招股说明书`, which matches the disclosure record's `secCode`.
3. **BSE legacy stock code** — pre-renumbering issuers carry a 新三板 `companyCd`
   (871263→920363, 873703→920703) that differs from the current 920xxx code.
   Issuer name from metadata became the authoritative identity signal; the
   legacy code is recorded, not treated as a mismatch.
4. **cninfo transient empty responses** — added discovery retry (3 attempts,
   backoff) plus an idempotent skip guard for rows already validated and
   SHA-verified on disk.

## Reproducibility

Raw PDFs (183 MB) are stored locally at `week10/acquisition/raw_pdf/` and are
git-ignored, following the repo's `data/prospectus_pdfs/*.pdf` convention.
Each manifest row records `source_url` + `sha256`, so every PDF is
reproducible without storing the binary in Git.

## Frozen inputs

- Manifest: `week10/acquisition/manifests/acquisition_manifest_v1.csv`
- Run log: `week10/acquisition/logs/acquire_results_v1.csv`
- Pipeline: `week10/acquisition/code/acquire.py` + `code/discovery/`
