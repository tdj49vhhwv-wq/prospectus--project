# Agent development workflow

This repository extracts financing history from IPO prospectuses. Explain results
in Chinese unless the user requests another language. Distinguish candidates,
validated records, Gold labels, and measured accuracy.

## Working safely

- Use the existing isolated checkout. Do not create a worktree unless requested.
- Check `git status` before editing; preserve user changes.
- Read the root README and the README for the affected week before choosing an
  entry point. Historical scripts are not interchangeable with current pipelines.
- Keep frozen parsers, blind-run records, Gold labels, and historical evaluation
  artifacts unchanged unless the user explicitly requests a revision. Write new
  experimental outputs outside those directories with a clearly identified run.
- Run Markdown extraction with `--no-db`. Do not contact PostgreSQL or call an
  LLM unless the task requires it. Check credential presence without printing
  values; never commit secrets, response logs containing secrets, or `.env`.

## Implementing and verifying changes

Reproduce bugs before editing. Trace the cause, make a focused change, and verify
the behavior users observe. Use the repository skills
`principle-prove-it-works` and `principle-test-behavior-not-implementation` as
guidance when relevant. They are a selected pstack subset, not the complete
Cursor plugin or its orchestration mode.

Install core dependencies with `bash scripts/setup_agent_env.sh`.
Run `./.venv/bin/python scripts/verify_agent_workflow.py` from the repository root.
This executes existing tests, an eight-company Markdown extraction, and the
frozen-parser investor evaluation. Outputs go to a temporary directory printed
by the runner; tracked historical outputs are not overwritten.

The initial baseline is 42 passed, 5 optional database tests skipped, and 1
failed test: `test_issued_shares_converted_to_wan` returns 24.3901 instead of
424.3901. Report this defect explicitly. Do not skip it, mark it xfail, relax its
assertion, or describe a failing run as green. A future bug-fix task should repair
the root cause. Frozen investor evaluation currently yields Gold 42, Auto 45,
TP 42, FP 3, FN 0, F1 96.55%; these are baseline results, not blind accuracy.

Before reporting completion, inspect the diff and report what changed, exact
checks executed, passed/failed/skipped outcomes, and remaining limitations.
Do not infer runtime correctness from syntax checks or a process ID. For research
or literature tasks, cite sources and distinguish source claims from inference.

GitHub Actions runs the same verifier. It intentionally remains failing while
the existing share-parsing defect is unresolved. Do not auto-merge or publish
research results merely because checks pass.
