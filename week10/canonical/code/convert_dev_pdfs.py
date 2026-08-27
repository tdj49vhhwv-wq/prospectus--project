#!/usr/bin/env python3
"""Stage 5C — canonicalization: convert DEV 12 prospectus PDFs to Markdown.

Uses MinerU 3.3.1 (the same conversion family as the original 25-company
corpus, which was produced by magic-pdf / MinerU). Output is written to
`week10/canonical/<stem>.md` so the Structure Profiler v2 reads a single
canonical text artifact per issuer, independent of MinerU's intermediate
working directory.

Concurrency is bounded (default 3) because MinerU's table/layout recognition
is CPU-heavy and parallel runs contend for memory.

Only DEV-role rows are converted. VAL and BLIND remain untouched.
"""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]          # repo root
MANIFEST = ROOT / "week10/acquisition/manifests/acquisition_manifest_v1.csv"
MARKDOWN_DIR = ROOT / "week10/acquisition/markdown"  # MinerU working dir
CANONICAL_DIR = ROOT / "week10/canonical"
LOG = ROOT / "week10/canonical/logs/convert_dev.log"

MINERU_ARGS = ["mineru", "-b", "pipeline", "-m", "txt", "-l", "ch"]

# MinerU 3.3.1 spawns a local FastAPI backend per invocation. Concurrent
# backends contend over the model cache / network and fail with SSL resets
# ("remote end closed connection"). Models are now cached on disk, so we run
# SEQUENTIALLY and force offline mode to avoid any network flakiness.
CONCURRENCY = 1

# Offline: models already cached under ~/.cache/modelscope + ~/.cache/huggingface.
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["MODELSCOPE_OFFLINE"] = "1"

# Transient failures ("All connection attempts failed", SSL resets) happen when
# MinerU's spawned local backend dies on startup. Retry with backoff before
# giving up; a leaked-semaphore crash is not a document problem.
MAX_ATTEMPTS = 3
RETRY_DELAY = 30  # seconds between retries


def clean(row: dict) -> dict:
    return {k.lstrip("﻿"): v for k, v in row.items()}


def load_rows(role: str = "DEV") -> list[dict]:
    with MANIFEST.open(newline="", encoding="utf-8") as f:
        rows = [clean(r) for r in csv.DictReader(f)]
    return [r for r in rows if r.get("role") == role]


def convert_one(row: dict) -> tuple[str, str]:
    """Run MinerU on one PDF, then move the .md to canonical. Returns (code, status)."""
    code = row["stock_code"]
    pdf_path = Path(row["pdf_path"])
    if not pdf_path.is_absolute():
        pdf_path = ROOT / pdf_path  # manifest stores repo-relative paths
    stem = pdf_path.stem  # e.g. 920002_万达轴承_招股说明书
    canonical_md = CANONICAL_DIR / f"{stem}.md"

    if canonical_md.exists() and canonical_md.stat().st_size > 0:
        return code, "already_done"

    # MinerU writes to MARKDOWN_DIR/<stem>/txt/<stem>.md (or a fallback path).
    candidates = [
        MARKDOWN_DIR / stem / "txt" / f"{stem}.md",
        MARKDOWN_DIR / stem / f"{stem}.md",
        MARKDOWN_DIR / stem / "auto" / f"{stem}.md",
    ]

    # If a prior run already produced a working .md (e.g. first smoke test),
    # reuse it instead of re-running MinerU.
    src = next((p for p in candidates if p.exists() and p.stat().st_size > 0), None)
    if src is None:
        src = next(
            (p for p in MARKDOWN_DIR.glob(f"{stem}/**/*.md")
             if p.stat().st_size > 0),
            None,
        )

    if src is None:
        last_err = ""
        for attempt in range(1, MAX_ATTEMPTS + 1):
            cmd = MINERU_ARGS + ["-p", str(pdf_path), "-o", str(MARKDOWN_DIR)]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode == 0:
                break
            last_err = proc.stderr.strip()[-300:]
            # clean partial working dir so a retry starts fresh
            workdir = MARKDOWN_DIR / stem
            if workdir.exists():
                shutil.rmtree(workdir, ignore_errors=True)
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_DELAY)
        else:
            return code, f"mineru_failed_after_{MAX_ATTEMPTS}: {last_err}"

        src = next((p for p in candidates if p.exists()), None)
        if src is None:
            src = next(MARKDOWN_DIR.glob(f"{stem}/**/*.md"), None)
        if src is None:
            return code, "no_md_output"

    CANONICAL_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, canonical_md)
    return code, f"ok ({canonical_md.stat().st_size} bytes)"


def main() -> None:
    ap = argparse.ArgumentParser(description="Convert prospectus PDFs to canonical Markdown via MinerU.")
    ap.add_argument("--role", default="DEV", choices=["DEV", "VAL", "BLIND"],
                    help="which sampling role to convert (default DEV)")
    args = ap.parse_args()

    CANONICAL_DIR.mkdir(parents=True, exist_ok=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)

    rows = load_rows(args.role)
    log = LOG.open("a", encoding="utf-8")
    log.write(f"\n=== run: {len(rows)} {args.role} rows, concurrency {CONCURRENCY} ===\n")

    results = {}
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        futs = {ex.submit(convert_one, r): r["stock_code"] for r in rows}
        for fut in as_completed(futs):
            code, status = fut.result()
            results[code] = status
            line = f"{code}: {status}"
            log.write(line + "\n")
            log.flush()
            print(line, flush=True)

    log.close()
    ok = sum(1 for s in results.values() if s.startswith("ok"))
    print(f"\nDONE: {ok}/{len(results)} converted successfully")


if __name__ == "__main__":
    sys.exit(main())
