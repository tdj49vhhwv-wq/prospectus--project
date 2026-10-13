#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
python3 -m venv .venv
requirements_file=$(mktemp)
trap 'rm -f "$requirements_file"' EXIT
python3 - "$requirements_file" <<'PY'
import sys
from pathlib import Path

# Paddle is optional per README; retain the repository's core version constraints.
lines = Path("week6/requirements.txt").read_text().splitlines(True)
Path(sys.argv[1]).write_text(
    "".join(line for line in lines if not line.startswith(("paddleocr", "paddlepaddle")))
)
PY
.venv/bin/python -m pip install --disable-pip-version-check --no-cache-dir -r "$requirements_file"
.venv/bin/python -m pip check
