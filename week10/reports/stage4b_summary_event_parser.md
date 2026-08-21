# Week 10 Stage 4B — Summary Event Parser v1

## Scope

Convert representation-agnostic structural blocks into event-level
candidates.

This stage does not yet classify PE/VC investors individually.

## Design

The parser uses generic signals:

- transaction date;
- increase / transfer / issuance language;
- investor action language;
- aggregate investment amount;
- shares issued;
- registered capital after the event;
- raw institutional list.

No company-name hardcodes are used.

## Precision protection

Blocks dominated by:

- verification reports;
- capital verification narrative;
- equity incentive;
- special-right / gambling agreement discussion;

receive negative confidence penalties.

## Next stage

Stage 4C expands `investor_list_raw` into normalized investor rows and
classifies institutional candidates.
