#!/usr/bin/env python3

import csv
import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

RESOLVED = (
    ROOT
    / "week10/acquisition/manifests/resolved_sources_v1.csv"
)

OUT_DIR = (
    ROOT
    / "week10/acquisition/raw_pdf"
)

LOG = (
    ROOT
    / "week10/acquisition/logs/download_results_v1.csv"
)

OUT_DIR.mkdir(parents=True, exist_ok=True)
LOG.parent.mkdir(parents=True, exist_ok=True)


def sha256(path):
    h = hashlib.sha256()

    with path.open("rb") as f:
        for block in iter(
            lambda: f.read(1024 * 1024),
            b""
        ):
            h.update(block)

    return h.hexdigest()


def is_pdf(path):
    try:
        with path.open("rb") as f:
            return f.read(5) == b"%PDF-"
    except Exception:
        return False


with RESOLVED.open(
    encoding="utf-8-sig"
) as f:
    rows = list(csv.DictReader(f))


results = []

print()
print("===== RESOLVED SOURCE DOWNLOAD =====")

for row in rows:

    code = row["stock_code"]
    company = row["company_name"]
    url = row["source_url"].strip()

    result = {
        "sample_id": row["sample_id"],
        "stock_code": code,
        "company_name": company,
        "source_url": url,
        "status": "",
        "pdf_path": "",
        "bytes": "",
        "sha256": "",
        "error": "",
    }

    print()
    print(code, company)

    if not url:
        result["status"] = "UNRESOLVED"
        result["error"] = "source_url empty"

        print("  UNRESOLVED")
        results.append(result)
        continue

    filename = (
        f"{code}_{company}_招股说明书.pdf"
    )

    out = OUT_DIR / filename
    tmp = OUT_DIR / (filename + ".part")

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent":
                "Mozilla/5.0 prospectus-research/1.0",
            "Accept":
                "application/pdf,*/*",
        },
    )

    try:
        with urllib.request.urlopen(
            req,
            timeout=45
        ) as resp:

            data = resp.read()

        tmp.write_bytes(data)

        if not is_pdf(tmp):
            raise RuntimeError(
                "downloaded content is not PDF"
            )

        size = tmp.stat().st_size

        # Prospectuses are normally large documents.
        # Reject tiny HTML/error-PDF responses.
        if size < 200_000:
            raise RuntimeError(
                f"PDF suspiciously small: {size} bytes"
            )

        tmp.replace(out)

        digest = sha256(out)

        result["status"] = "DOWNLOADED"
        result["pdf_path"] = str(
            out.relative_to(ROOT)
        )
        result["bytes"] = size
        result["sha256"] = digest

        print("  DOWNLOADED")
        print("  bytes :", size)
        print("  sha256:", digest)
        print(
            "  path   :",
            out.relative_to(ROOT)
        )

    except Exception as e:

        if tmp.exists():
            tmp.unlink()

        result["status"] = "FAILED"
        result["error"] = repr(e)

        print(
            "  FAILED:",
            repr(e)
        )

    results.append(result)


fields = [
    "sample_id",
    "stock_code",
    "company_name",
    "source_url",
    "status",
    "pdf_path",
    "bytes",
    "sha256",
    "error",
]

with LOG.open(
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:

    w = csv.DictWriter(
        f,
        fieldnames=fields
    )

    w.writeheader()
    w.writerows(results)


print()
print("===== DOWNLOAD SUMMARY =====")

for r in results:
    print(
        r["stock_code"],
        r["company_name"],
        r["status"]
    )

print()
print(
    "Output:",
    LOG.relative_to(ROOT)
)
