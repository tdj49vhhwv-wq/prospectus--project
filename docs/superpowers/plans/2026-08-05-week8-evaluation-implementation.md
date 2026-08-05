# Week 8 Evaluation Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, evidence-traceable evaluation pipeline that freezes Gold v1.1, evaluates event-level and investor-row-level extraction, normalizes core fields, and produces a reproducible Week 8 baseline for the existing eight-company development set.

**Architecture:** Keep evaluation independent from the database and LLM layers. Load the verified row-level Gold JSONL from `week3/manual_gold`, normalize both Gold and Markdown candidates into small immutable records, use deterministic one-to-one bipartite matching with explicit match reasons, then aggregate metrics and field completeness into versioned CSV/JSON/Markdown reports. Event evaluation collapses investor rows by company/date/event type; investor evaluation matches names only inside compatible events.

**Tech Stack:** Python 3.9 standard library, `pytest` for tests, existing Week 6 Markdown extractor as the candidate source.

## Global Constraints

- Existing eight companies are the development set; no future blind-test company may influence Week 8 rules.
- The formal baseline uses deterministic code only; no database connection and no LLM call.
- Gold changes are append-only in a change log; the Week 3 source file is never overwritten.
- Every TP, FP, and FN must retain Auto/Gold identifiers and source evidence.
- Missing values remain missing and are never replaced with zero.
- Dates and amounts are required normalization targets; shares and price require reliable normalization status and failure reasons but not high coverage.
- No minimum F1 is invented before the first strict baseline is measured.

---

### Task 1: Freeze and Audit Gold v1.1

**Files:**
- Create: `week8/gold/build_gold_v1_1.py`
- Create: `week8/gold/gold_definition_v1.1.md`
- Create: `week8/gold/gold_change_log.csv`
- Create: `week8/gold/subscription_flow_gold_v1.1.jsonl`
- Test: `week8/tests/test_gold_builder.py`

**Interfaces:**
- Consumes: `week3/manual_gold/subscription_flow_gold.jsonl`.
- Produces: `build_gold(source: Path, output: Path) -> dict` and 124 JSONL rows with stable `gold_id`, `gold_version`, `review_status`, and preserved evidence.

- [ ] **Step 1: Write failing tests for stable IDs, 124-row preservation, required evidence, and source immutability**

```python
def test_build_gold_preserves_rows_and_adds_stable_ids(tmp_path):
    summary = build_gold(SOURCE_GOLD, tmp_path / "gold.jsonl")
    rows = load_jsonl(tmp_path / "gold.jsonl")
    assert summary["rows"] == 124
    assert len({row["gold_id"] for row in rows}) == 124
    assert all(row["gold_version"] == "1.1" for row in rows)
    assert all(row["evidence_text"].strip() for row in rows)
```

- [ ] **Step 2: Run the tests and confirm they fail because the builder does not exist**

Run: `python3 -m pytest week8/tests/test_gold_builder.py -q`

- [ ] **Step 3: Implement the minimal deterministic builder and audit summary**

Stable ID format: `GOLD-{stock_code}-{subscription_date or unknown}-{sequence:03d}`. Preserve all original fields, add metadata only, and fail on missing stock code, subscriber, or evidence.

- [ ] **Step 4: Run tests, build Gold v1.1, and verify source SHA-256 is unchanged**

Run: `python3 -m pytest week8/tests/test_gold_builder.py -q && python3 week8/gold/build_gold_v1_1.py`

- [ ] **Step 5: Commit**

```bash
git add week8/gold week8/tests/test_gold_builder.py
git commit -m "feat: freeze auditable Gold v1.1"
```

### Task 2: Normalize Dates, Names, Event Types, and Numeric Fields

**Files:**
- Create: `week8/evaluation/__init__.py`
- Create: `week8/evaluation/normalize.py`
- Create: `week8/evaluation/investor_aliases.csv`
- Create: `week8/normalization_rules.md`
- Test: `week8/tests/test_normalize.py`

**Interfaces:**
- Produces: `normalize_date(value) -> NormalizedValue`, `normalize_number(value, unit) -> NormalizedValue`, `normalize_name(value, aliases) -> str`, and `normalize_event_type(value) -> str`.
- `NormalizedValue` contains `raw`, `value`, `status`, `precision`, and `reason`.

- [ ] **Step 1: Write failing table-driven tests for exact/day/month/year dates, Chinese units, commas, nulls, aliases, and event mappings**

```python
@pytest.mark.parametrize(("raw", "value", "precision"), [
    ("2021-08-25", "2021-08-25", "day"),
    ("2021年8月", "2021-08", "month"),
    ("2018", "2018", "year"),
])
def test_normalize_date_preserves_disclosed_precision(raw, value, precision):
    result = normalize_date(raw)
    assert (result.value, result.precision) == (value, precision)
```

- [ ] **Step 2: Run tests and verify the expected missing-module failure**

Run: `python3 -m pytest week8/tests/test_normalize.py -q`

- [ ] **Step 3: Implement minimal normalization without guessing undisclosed precision**

Names remove Unicode/ASCII spacing and normalize bracket shapes, but do not remove meaningful legal-entity text. Numeric normalization accepts the unit explicitly and never infers a unit from an absent label.

- [ ] **Step 4: Run normalization tests and the existing Week 6 regression suite**

Run: `python3 -m pytest week8/tests/test_normalize.py week6/tests week6/pipeline/test_vie_regression.py -q`

- [ ] **Step 5: Commit**

```bash
git add week8/evaluation week8/tests/test_normalize.py week8/normalization_rules.md
git commit -m "feat: add traceable field normalization"
```

### Task 3: Implement Event-Level One-to-One Evaluation

**Files:**
- Create: `week8/evaluation/io.py`
- Create: `week8/evaluation/event_evaluator.py`
- Create: `week8/matching_spec.md`
- Test: `week8/tests/test_event_evaluator.py`

**Interfaces:**
- Consumes normalized Gold rows and Auto rows.
- Produces: `evaluate_events(gold_rows, auto_rows) -> EvaluationResult`, where result contains `matches`, `false_positives`, `false_negatives`, and metric groups for overall/company/event type.

- [ ] **Step 1: Write failing tests for exact match, month/day compatibility, wrong company, wrong type, duplicate Auto, and zero-denominator metrics**

```python
def test_duplicate_auto_can_match_one_gold_only():
    result = evaluate_events([gold("001282", "2020-05", "增资")], [
        auto("001282", "2020-05-03", "增资", "A1"),
        auto("001282", "2020-05-03", "增资", "A2"),
    ])
    assert (result.tp, result.fp, result.fn) == (1, 1, 0)
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `python3 -m pytest week8/tests/test_event_evaluator.py -q`

- [ ] **Step 3: Implement deterministic compatible-pair scoring and greedy one-to-one assignment**

Compatibility requires stock code and normalized event type. Date scoring is exact day > same month > same year only when Gold has that disclosed precision. Tie-break by Auto ID then Gold ID for deterministic output.

- [ ] **Step 4: Run tests and mutation-check duplicate handling, type checking, and N/A metrics**

Run: `python3 -m pytest week8/tests/test_event_evaluator.py -q`

- [ ] **Step 5: Commit**

```bash
git add week8/evaluation week8/tests/test_event_evaluator.py week8/matching_spec.md
git commit -m "feat: add strict event-level evaluator"
```

### Task 4: Implement Investor-Row Evaluation Inside Compatible Events

**Files:**
- Create: `week8/evaluation/investor_evaluator.py`
- Test: `week8/tests/test_investor_evaluator.py`

**Interfaces:**
- Produces: `evaluate_investors(gold_rows, auto_rows, aliases) -> EvaluationResult`.
- A row can be a TP only when company, compatible date/type, and normalized investor identity all match; numeric fields are reported separately and do not manufacture identity matches.

- [ ] **Step 1: Write failing tests for aliases, multiple investors in one round, non-investor entities, duplicate candidates, and field-level missingness**

```python
def test_two_investors_in_one_event_are_scored_separately():
    result = evaluate_investors(
        [gold_row("稳正景明"), gold_row("长泽创投")],
        [auto_row("深圳市稳正景明创业投资企业（有限合伙）")],
        aliases={"稳正景明": "深圳市稳正景明创业投资企业(有限合伙)"},
    )
    assert (result.tp, result.fp, result.fn) == (1, 0, 1)
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `python3 -m pytest week8/tests/test_investor_evaluator.py -q`

- [ ] **Step 3: Implement minimal one-to-one investor matching and field status reporting**

For amount/shares/price use exact-or-0.5%-relative tolerance when both sides disclose a value; report `auto_missing`, `gold_not_disclosed`, or `mismatch` otherwise.

- [ ] **Step 4: Run all Week 8 and legacy tests**

Run: `python3 -m pytest week8/tests week6/tests week6/pipeline/test_vie_regression.py -q`

- [ ] **Step 5: Commit**

```bash
git add week8/evaluation/investor_evaluator.py week8/tests/test_investor_evaluator.py
git commit -m "feat: add investor-row evaluator"
```

### Task 5: Build the Reproducible Baseline Command and Reports

**Files:**
- Create: `week8/run_week8_evaluation.py`
- Create: `week8/results/.gitkeep`
- Create: `week8/tests/test_run_evaluation.py`
- Modify: `week8/week8_plan.md`
- Modify: `README.md`
- Generate: `week8/results/event_matches.csv`
- Generate: `week8/results/investor_matches.csv`
- Generate: `week8/results/event_metrics.json`
- Generate: `week8/results/investor_metrics.json`
- Generate: `week8/results/field_completeness.csv`
- Generate: `week8/results/error_analysis.md`
- Generate: `week8/week8_summary.md`

**Interfaces:**
- Command: `python3 week8/run_week8_evaluation.py`.
- Default inputs: Gold v1.1 and in-memory output from the existing Markdown extractor.
- Default behavior: no DB connection, no API call, deterministic output excluding volatile timestamps.

- [ ] **Step 1: Write a failing integration test using tiny temporary Gold/Auto JSONL fixtures**

```python
def test_cli_writes_traceable_metrics_and_error_files(tmp_path):
    completed = run_cli(tmp_path, gold_fixture, auto_fixture)
    assert completed.returncode == 0
    metrics = json.loads((tmp_path / "event_metrics.json").read_text())
    assert metrics["overall"] == {"tp": 1, "fp": 1, "fn": 1, "precision": 0.5, "recall": 0.5, "f1": 0.5}
    assert (tmp_path / "event_errors.csv").exists()
```

- [ ] **Step 2: Run the integration test and verify RED**

Run: `python3 -m pytest week8/tests/test_run_evaluation.py -q`

- [ ] **Step 3: Implement the command, CSV/JSON writers, hashes, and Markdown summary**

The command accepts `--gold`, `--auto`, and `--output-dir` for tests and blind samples. Without `--auto`, it imports the existing Markdown extractor and generates all 645 candidates in memory.

- [ ] **Step 4: Run the full eight-company baseline twice and compare output hashes**

Run: `python3 week8/run_week8_evaluation.py && shasum -a 256 week8/results/*`

- [ ] **Step 5: Inspect FP/FN Top 10, document Gold disputes separately, and make only evidence-backed extraction fixes with new failing tests**

Any extraction fix must live behind a test reproducing the specific false entity, duplicate, or missed event. Re-run the baseline and record before/after metrics without deleting the original baseline values.

- [ ] **Step 6: Run final verification and commit**

```bash
python3 -m pytest week8/tests week6/tests week6/pipeline/test_vie_regression.py -q
git diff --check
git add week8 README.md
git commit -m "feat: deliver reproducible Week 8 baseline"
```

