#!/usr/bin/env python3
"""Week 10 Stage 5B.4 — conservative official-source resolver.

The resolver is intentionally fail-closed.  It accepts manually supplied or
machine-discovered candidate URLs, scores them, and writes a resolved manifest
only when the candidate satisfies strict exchange/issuer/document checks.

Discovery adapters can be extended independently for SSE/SZSE/BSE without
changing downstream acquisition semantics.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "week10/acquisition/manifests/acquisition_manifest_v1.csv"
OUT_DIR = ROOT / "week10/acquisition/resolver_v1"

OFFICIAL_HOSTS = {
    "SSE": ("sse.com.cn",),
    "SZSE": ("szse.cn",),
    "BSE": ("bse.cn",),
}
DOC_TERMS = ("招股说明书", "招股书")
NEGATIVE_TERMS = ("摘要", "提示性公告", "上市公告书", "发行结果", "询价", "路演")

@dataclass
class Candidate:
    stock_code: str
    company_name: str
    exchange: str
    url: str
    title: str = ""
    source: str = "candidate"
    score: int = 0
    official_host: bool = False
    code_match: bool = False
    company_match: bool = False
    prospectus_match: bool = False
    negative_match: bool = False
    status: str = "candidate_needs_validation"
    reasons: str = ""


def host_is_official(exchange: str, url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in OFFICIAL_HOSTS.get(exchange, ()))


def normalize(s: str) -> str:
    return re.sub(r"\s+", "", s or "").lower()


def evaluate(row: dict, raw: dict) -> Candidate:
    c = Candidate(
        stock_code=row["stock_code"].strip(),
        company_name=row["company_name"].strip(),
        exchange=row["exchange"].strip(),
        url=(raw.get("url") or "").strip(),
        title=(raw.get("title") or "").strip(),
        source=(raw.get("source") or "candidate").strip(),
    )
    hay = normalize(c.title + " " + c.url)
    c.official_host = host_is_official(c.exchange, c.url)
    c.code_match = normalize(c.stock_code) in hay
    c.company_match = normalize(c.company_name) in hay
    c.prospectus_match = any(normalize(t) in hay for t in DOC_TERMS)
    c.negative_match = any(normalize(t) in hay for t in NEGATIVE_TERMS)

    score = 0
    reasons = []
    if c.official_host:
        score += 5; reasons.append("official_host")
    if c.company_match:
        score += 4; reasons.append("company_match")
    if c.code_match:
        score += 3; reasons.append("code_match")
    if c.prospectus_match:
        score += 4; reasons.append("prospectus_match")
    if c.url.lower().endswith(".pdf") or ".pdf?" in c.url.lower():
        score += 1; reasons.append("pdf_url")
    if c.negative_match:
        score -= 8; reasons.append("negative_title")
    c.score = score
    c.reasons = "|".join(reasons)

    # A URL is automatically accepted only if it is on an official exchange
    # host and the supplied metadata proves issuer + prospectus identity.
    if c.official_host and c.company_match and c.prospectus_match and not c.negative_match:
        c.status = "resolved_official"
    else:
        c.status = "candidate_needs_validation"
    return c


def load_candidates(path: Path | None) -> list[dict]:
    if path is None or not path.exists():
        return []
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--candidates", type=Path, default=None,
                    help="CSV/JSONL candidate URLs from exchange adapters or reviewed search results")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with args.manifest.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    candidates = load_candidates(args.candidates)
    by_code: dict[str, list[dict]] = {}
    for c in candidates:
        by_code.setdefault((c.get("stock_code") or "").strip(), []).append(c)

    diagnostics = []
    resolved_rows = []
    for row in rows:
        code = row["stock_code"].strip()
        evaluated = [evaluate(row, x) for x in by_code.get(code, []) if (x.get("url") or "").strip()]
        evaluated.sort(key=lambda x: x.score, reverse=True)
        diagnostics.extend(asdict(x) for x in evaluated)
        accepted = next((x for x in evaluated if x.status == "resolved_official"), None)

        out = dict(row)
        if accepted:
            out["source_url"] = accepted.url
            out["source_type"] = "official_exchange"
            out["download_status"] = "resolved"
            out["notes"] = (out.get("notes", "") + f"; resolver_v1 score={accepted.score}").strip("; ")
        else:
            out["download_status"] = "needs_resolution"
            out["notes"] = (out.get("notes", "") + "; resolver_v1 fail-closed").strip("; ")
        resolved_rows.append(out)

    diag_path = OUT_DIR / "candidate_diagnostics_v1.csv"
    diag_fields = list(Candidate.__dataclass_fields__)
    with diag_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=diag_fields); w.writeheader(); w.writerows(diagnostics)

    out_path = OUT_DIR / "acquisition_manifest_resolved_v1.csv"
    fields = list(rows[0].keys()) if rows else []
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(resolved_rows)

    resolved = sum(r.get("download_status") == "resolved" for r in resolved_rows)
    print("===== STAGE 5B.4 RESOLVER =====")
    print(f"Rows: {len(resolved_rows)}")
    print(f"Candidates evaluated: {len(diagnostics)}")
    print(f"Resolved official: {resolved}")
    print(f"Needs resolution: {len(resolved_rows) - resolved}")
    print(f"Output: {out_path.relative_to(ROOT)}")
    print(f"Diagnostics: {diag_path.relative_to(ROOT)}")

if __name__ == "__main__":
    main()
