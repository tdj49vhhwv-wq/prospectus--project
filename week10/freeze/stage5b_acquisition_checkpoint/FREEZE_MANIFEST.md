# Week 10 Stage 5B — Acquisition Checkpoint (frozen)

## Status

24 / 24 frozen independent-sample prospectuses `downloaded_validated`,
SHA256-verified on disk.

## Scope boundary

Stage 5B covers acquisition only: discovery, download, transport +
identity validation, SHA256, manifest writeback. No document-level PE/VC
content has been read or extracted from any of the 24 prospectuses.

## Frozen artifacts

- Manifest (24 rows, source_url + sha256): `acquisition/manifests/acquisition_manifest_v1.csv`
- Run log: `acquisition/logs/acquire_results_v1.csv`
- Pipeline: `acquisition/code/acquire.py` + `acquisition/code/discovery/`
- Checkpoint report: `reports/stage5b_acquisition_checkpoint.md`

## Reproducibility

Raw PDFs (183 MB) are git-ignored. Every row records `source_url` + `sha256`;
re-download and re-verify with `python3 acquisition/code/acquire.py`.

## Next stage

Stage 5C — Canonicalization + Independent Structure Profiling (DEV 12 only).
BLIND 6 remain untouched.
