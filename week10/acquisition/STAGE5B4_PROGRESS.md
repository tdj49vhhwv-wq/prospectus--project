# Week 10 Stage 5B.4 — Official Resolver Progress

## Current state

The acquisition resolver remains fail-closed. Smoke-test issuers:

- 603312 西典新能 — SSE — target disclosure date 2024-01-08
- 301536 星宸科技 — SZSE — target disclosure date 2024-03-22
- 920002 万达轴承 — BSE — target disclosure date 2024-05-17

## Implemented in this branch

1. `discovery_adapters_v1.py`: independent SSE/SZSE/BSE discovery adapters.
2. `resolve_official_sources_v1.py`: official-host + issuer + prospectus-title candidate gate.
3. `download_validate_v1.py`: HTTP/PDF-magic/min-size validation, first-page text extraction, prospectus + issuer + stock-code validation, SHA256, manifest update.
4. `run_acquisition_v1.py`: one-command discovery -> merge -> resolver -> download/validate orchestration.
5. `.github/workflows/week10_stage5b4.yml`: reproducible GitHub Actions smoke test with diagnostic artifacts.
6. `resolver_hints_smoke_v1.csv`: independently verified official-domain hints plus a deliberate BSE negative control.

## Verified official discovery

### SSE / 603312 西典新能

Verified official SSE PDF:
`https://static.sse.com.cn/stock/disclosure/announcement/c/202302/001582_20230228_7BEU.pdf`

Its content identifies `苏州西典新能源电气股份有限公司 招股说明书（申报稿）`. It is retained as an official fallback discovery candidate, explicitly tagged as 申报稿 rather than silently substituted for the final 2024 issuance prospectus.

### SZSE / 301536 星宸科技

Verified official SZSE registration-draft PDF:
`https://reportdocs.static.szse.cn/UpFiles/rasinfodisc1/202309/RAS_202309_D62095CA75574CFCB2C5871C86947137.pdf`

The document identifies `星宸科技股份有限公司首次公开发行股票并在创业板上市招股说明书（注册稿）`. Official SZSE issuance materials separately confirm stock code 301536 and the March 2024 issuance timeline.

### BSE / 920002 万达轴承

The exact final BSE prospectus URL remains unresolved. The official 2024-05-27 listing announcement is included only as a negative-control candidate and must be rejected because its document type is `上市公告书`, not `招股说明书`.

Independent discovery confirms the final prospectus content has security code 920002, issue price 20.74 yuan, expected issue date 2024-05-21, and prospectus signing date 2024-05-20; a later official BSE report explicitly states that the prospectus was disclosed on 2024-05-17. These facts are discovery evidence only and do not replace an official BSE canonical URL.

## Acceptance gates

A corpus PDF must pass all gates:

`expected official host -> HTTP 200 -> %PDF- -> >=200 KB -> parseable PDF -> 招股说明书 text -> issuer match -> stock-code match -> SHA256`

Any failure yields `needs_resolution` or `validation_failed`; no silent replacement is allowed.

## Expansion policy

The frozen 24-company manifest will be passed into the same pipeline only after the 3-company smoke test demonstrates that all three exchange routes can resolve and validate correctly. DEV/VAL/BLIND roles remain unchanged; historical blind cases 688795/688802 are not used for tuning.
