# Formal Blind Run #1 — Gold Audit and Evaluation

## 1. Protocol

Blind Run #1 is evaluated against a manually constructed, prospectus-grounded PE/VC Gold Standard created **after** the Stage 7.1 parser was frozen.

The PE/VC scope follows the Week 9 frozen definition:

- include institutional investors explicitly participating in financing / capital increase rounds, including PE, VC, CVC, strategic institutions, government/state-backed investment institutions and other institutional financing participants;
- exclude ordinary natural persons, founders/controllers when acting as individuals, issuer employee shareholding platforms, and non-financing restructuring-only shareholders;
- prospectus-defined abbreviations are treated as entity aliases, but uncontrolled fuzzy matching is not used.

Specific audit exclusions in 沐曦股份 include natural-person investors `葛卫东` and `戎艳琳`, and `晖泽共广`, which the prospectus identifies as an employee co-investment platform of its manager.

## 2. Gold Construction

### 688795 摩尔线程

Gold PE/VC investor-event rows: **47**.

- 2022-12, first report-period transfer + capital increase: 4 institutional subscribers.
- 2023-10, second capital increase: 5 institutional subscribers.
- 2024-12, third / Pre-IPO capital increase: 38 institutional subscribers.

### 688802 沐曦股份

Gold PE/VC investor-event rows: **114**.

The prospectus states that the report period contains seven capital increases. The Gold Standard covers the explicit institutional subscribers in 2022-09, 2023-02, 2023-04, 2023-12, 2024-08, 2025-02 and 2025-03.

## 3. Blind Run #1 Result

| Metric | Result |
|---|---:|
| Gold PE/VC rows | 161 |
| Auto PE/VC rows | 7 |
| TP | 7 |
| FP | 0 |
| FN | 154 |
| Precision | 100.00% |
| Recall | 4.35% |
| F1 | 8.33% |

By company:

- 摩尔线程: 47 Gold rows; the frozen parser returned 7 rows, all valid, leaving 40 FN.
- 沐曦股份: 114 Gold rows; the frozen parser returned 0 rows, leaving 114 FN.

## 4. Interpretation

Blind Run #1 demonstrates **high precision but severe recall failure**. The Stage 7.1 development-set freeze generalized conservatively: it did not hallucinate PE/VC rows in the two blind companies, but it missed most valid financing participants.

The dominant blind failure modes are structural rather than entity-name errors:

1. **Long aggregate investor lists.** 沐曦股份 summarizes several financing rounds as large comma-separated investor lists rather than the shorter transaction clauses dominant in the development set.
2. **Aggregate subscription records.** Several rounds disclose a total investment amount / total newly issued shares for a group, without row-level amounts per investor.
3. **Large Pre-IPO syndicates.** 摩尔线程's 2024-12 round contains 38 subscribers represented as one defined group (Pre-IPO轮股东), which the frozen event-local parser did not expand.
4. **Table-summary layout differences.** 沐曦股份 compresses seven capital increases into a report-period equity-change summary table. The frozen parser is too dependent on heading/transaction-clause structures learned from the Dev set.

## 5. Integrity Rule

The raw Blind Run #1 output is immutable. No post-blind parser revision may overwrite or relabel these results.

Any change informed by this error analysis begins **Week 10 / Post-Blind Revision** and must produce a separately labelled `Blind Run #2`.
