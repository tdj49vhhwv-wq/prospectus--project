# Week 9 Formal Blind Run #1

## Freeze status before blind run
- Core Event Precision: 90.24%
- Core Event Recall: 92.50%
- PE/VC-focused Investor Precision: 93.02%
- PE/VC-focused Investor Recall: 95.24%
- PE/VC-focused Investor F1: 94.12%
- Freeze Gate: PASS

## Frozen parser
- `stage71_frozen/event_local_pevc.py`
- SHA256: `66a80a6f89f2b29de394a26292324db4b8e94f48a823531c2b921b049f2d11df`

## Blind companies
- 688795 摩尔线程
- 688802 沐曦股份

## Blind Run #1 raw outcomes
- 688795 base validated events: 13
- 688795 PE/VC event-local rows: 7
- 688802 base validated events: 4
- 688802 PE/VC event-local rows: 0

The first-run outputs are preserved unchanged. No blind-result-driven modification to the frozen extraction rules was made before or during this run.

The offline environment lacked `pg8000`; a no-DB compatibility stub was added solely to allow execution with `--no-db`. It did not change extraction logic.
