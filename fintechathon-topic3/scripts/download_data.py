"""Fetch the exact research subset and verify SHA256; no platform scraping."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "e5b82be3c909f9bb45dfd03e164ae0b7897832bd"
BASE = f"https://raw.githubusercontent.com/ahegel/yelp-dataset/{COMMIT}/"
FILES = {
    "cleveland_business.jsonl": ("data/business_sample_cleveland.json", "c0d2cd404c3f2b1c87673eb9dc9ce407fdcf3b49aab8cd631dc785672f7a0bd2"),
    "cleveland_reviews.jsonl": ("data/review_sample_cleveland.json", "fb80a0cc7bfd27bef27fbb8c11c632ebe928fa8c32c899fbedd0872ec416d0dd"),
}


def main():
    (ROOT / "data").mkdir(exist_ok=True)
    sources = []
    for filename, (remote_path, expected) in FILES.items():
        destination = ROOT / "data" / filename
        url = BASE + remote_path
        if not destination.exists():
            temporary = destination.with_suffix(".download")
            with requests.get(url, stream=True, timeout=(20, 90)) as response:
                response.raise_for_status()
                with temporary.open("wb") as out:
                    for chunk in response.iter_content(1024 * 1024):
                        out.write(chunk)
            digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
            if digest != expected:
                raise RuntimeError(f"Checksum mismatch for {filename}; unverified .download retained, not used")
            temporary.rename(destination)
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        if digest != expected:
            raise RuntimeError(f"Existing {filename} differs from pinned input; preserve it and investigate")
        sources.append({"file": filename, "url": url, "sha256": digest, "bytes": destination.stat().st_size})
        print(filename, "verified", destination.stat().st_size, flush=True)
    manifest = {
        "verified_at_Asia_Shanghai": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "original_source": "https://www.yelp.com/dataset",
        "download_source": "third-party academic Cleveland subset on GitHub; not an official Yelp download",
        "repository": "https://github.com/ahegel/yelp-dataset",
        "commit": COMMIT,
        "sampling_documentation": BASE + "create_sample_data.py",
        "sampling_rule": "original published filter: city.str.contains('leveland'); data represent the source's regional subset",
        "license_status": "UNCONFIRMED for current terms and this mirror's redistribution permission. Official endpoints were blocked by environment egress proxy. A 2015 academic-only agreement was archived as historical context, not proof of a current license or of permission to redistribute this 2017-review subset.",
        "license_action": "Read the current official Yelp dataset terms and confirm this educational competition use is covered before submitting or sharing derived outputs. Do not redistribute raw merchant records, reviews or reviewer information.",
        "business_status_capture_date": "not documented by the subset source",
        "files": sources,
    }
    (ROOT / "sources/data_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
