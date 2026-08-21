# Week 10 Stage 5 Independent Sampling Rules

## Prespecified sample

24 new prospectuses were selected before document-level PE/VC
extraction and annotation.

Distribution:

- Main Board: 8
- ChiNext: 8
- BSE: 8

Experimental roles:

- DEV: 12
- VAL: 6
- BLIND: 6

## Experimental discipline

DEV:
May be inspected and used for parser/classifier development.

VAL:
May be used for architecture and threshold selection, but should
not be used to create company-specific rules.

BLIND:
Must not be used for parser, router, threshold, or PE/VC classifier
development.

PE/VC gold labels for BLIND documents must remain unavailable to
the extraction pipeline until the final evaluation.

## Replacement rule

A prespecified company may only be replaced when the target
prospectus cannot be obtained from an authoritative/reliable
public source or the source document is technically unusable.

Poor extraction performance, unusual document structure, absence
of PE/VC investors, or difficult cases are NOT valid replacement
reasons.

Every replacement must be documented before analysis.
