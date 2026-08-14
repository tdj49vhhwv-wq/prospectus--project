# Week 9 Pipeline Freeze

Freeze gate (Dev 8):
- Core Event Precision: 90.24%
- Core Event Recall: 92.50%
- PE/VC-focused Investor: TP=40, FP=3, FN=2
- PE/VC Precision: 93.02%
- PE/VC Recall: 95.24%
- PE/VC F1: 94.12%
- Gate: PASS

Protocol:
- Event logic frozen from the stable Week 9 development pipeline.
- PE/VC investor parser uses event-local transaction blocks only.
- Formal headings override Mermaid evidence; Mermaid is fallback only when no formal event section exists.
- Investor identities require transaction structure (subscription/contribution/issuance), followed by institution/entity filtering.
- Prospectus-defined aliases are used for entity normalization.
- No blind-test result may be used to modify the frozen logic before Blind Run #1 is recorded.
