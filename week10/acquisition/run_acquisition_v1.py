#!/usr/bin/env python3
"""Orchestrate Stage 5B.4: discovery -> candidate merge -> resolver -> download validator."""
from __future__ import annotations
import argparse, csv, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ACQ = ROOT / "week10/acquisition"
DEFAULT_MANIFEST = ACQ / "manifests/acquisition_manifest_v1.csv"
DEFAULT_HINTS = ACQ / "manifests/resolver_hints_smoke_v1.csv"
DISCOVERED = ACQ / "resolver_v1/discovered_candidates_v1.csv"
MERGED = ACQ / "resolver_v1/resolver_candidates_merged_v1.csv"
RESOLVED = ACQ / "resolver_v1/acquisition_manifest_resolved_v1.csv"


def run(*args: str) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.run(args, cwd=ROOT, check=True)


def read_csv(path: Path):
    if not path.exists(): return []
    with path.open(encoding="utf-8-sig", newline="") as f: return list(csv.DictReader(f))


def merge_candidates(hints: Path) -> None:
    rows = []
    for r in read_csv(DISCOVERED):
        if (r.get("url") or "").strip():
            rows.append({"stock_code": r.get("stock_code", ""), "url": r.get("url", ""), "title": r.get("title", ""), "source": r.get("source", "")})
    for r in read_csv(hints):
        if (r.get("url") or "").strip():
            rows.append({"stock_code": r.get("stock_code", ""), "url": r.get("url", ""), "title": r.get("title", ""), "source": r.get("source", "")})
    seen = set(); out=[]
    for r in rows:
        key=(r["stock_code"],r["url"])
        if key not in seen: seen.add(key); out.append(r)
    MERGED.parent.mkdir(parents=True, exist_ok=True)
    with MERGED.open("w", encoding="utf-8-sig", newline="") as f:
        w=csv.DictWriter(f, fieldnames=["stock_code","url","title","source"]); w.writeheader(); w.writerows(out)
    print("Merged candidates:", len(out))


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--hints", type=Path, default=DEFAULT_HINTS)
    ap.add_argument("--skip-download", action="store_true")
    args=ap.parse_args()

    run(sys.executable, str(ACQ/"discovery_adapters_v1.py"), "--manifest", str(args.manifest), "--out", str(DISCOVERED))
    merge_candidates(args.hints)
    run(sys.executable, str(ACQ/"resolve_official_sources_v1.py"), "--manifest", str(args.manifest), "--candidates", str(MERGED))
    if not args.skip_download:
        run(sys.executable, str(ACQ/"download_validate_v1.py"), "--manifest", str(RESOLVED))

if __name__ == "__main__": main()
