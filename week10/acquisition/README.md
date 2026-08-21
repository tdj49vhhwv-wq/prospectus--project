# Week 10 Stage 5B — Prospectus Acquisition

## Objective

Build a reproducible acquisition pipeline:

sampling manifest
→ official disclosure discovery
→ prospectus PDF
→ SHA256
→ Markdown
→ canonical source registry
→ Structure Profiler

## Source priority

1. Official exchange disclosure source
2. Official issuer / regulatory disclosure source when necessary
3. Other public mirrors only for diagnosis, not as preferred canonical sources

## Experimental discipline

DEV documents may be inspected during development.

VAL documents are acquired only after the acquisition pipeline is stable.

BLIND documents must not be used for parser/classifier development.

Acquisition failures must be logged and must not silently trigger
sample replacement.

## Stage 5B.1 smoke test

- 603312 西典新能 — SSE Main — DEV
- 301536 星宸科技 — SZSE ChiNext — DEV
- 920002 万达轴承 — BSE — DEV
