"""
Stage 1a (unstructured source): Pull real-world security advisories.

Unlike ATT&CK/CAPEC/CWE (structured databases), GitHub Security Advisories
contain genuine free-text descriptions written by humans -- e.g. "An attacker
with local access could exploit a race condition in the token refresh logic
to escalate privileges..." -- which is exactly the kind of raw prose the
paper's Stage 1 LLM extraction step is meant to process. This is the actual
input to extract_triplets_llm.py.

NOTE: this script could not be run to completion in the sandbox this project
was built in -- api.github.com rate-limits unauthenticated requests (60/hr)
and the sandbox's shared IP had already exhausted that limit. It should work
immediately from your own machine. If you hit the same rate limit, add a
GitHub personal access token (no special scopes needed, just "public repo"
read) via the Authorization header -- see the commented-out line below.
"""
import sys
import json
import time
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import GITHUB_ADVISORIES_API, RAW_DIR

NUM_ADVISORIES = 100          # start small -- each one becomes an LLM extraction call later
PER_PAGE = 25


def download_advisories(num_advisories=NUM_ADVISORIES) -> Path:
    out_path = RAW_DIR / "github_advisories.json"
    headers = {"Accept": "application/vnd.github+json"}
    # If you hit a 403 rate-limit error, uncomment and fill in a token:
    # headers["Authorization"] = "Bearer ghp_your_token_here"

    all_advisories = []
    page = 1
    print(f"Fetching security advisories from:\n  {GITHUB_ADVISORIES_API}")
    while len(all_advisories) < num_advisories:
        resp = requests.get(
            GITHUB_ADVISORIES_API,
            headers=headers,
            params={"per_page": PER_PAGE, "page": page, "sort": "published", "direction": "desc"},
            timeout=30,
        )
        if resp.status_code == 403:
            print(f"\nRate-limited by GitHub at {len(all_advisories)} advisories fetched so far.")
            print("Either wait an hour, or add a personal access token (see script comments).")
            break
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        all_advisories.extend(batch)
        print(f"  fetched page {page} ({len(batch)} advisories, {len(all_advisories)} total)")
        page += 1
        time.sleep(0.5)  # be polite to the unauthenticated rate limit

    # Keep only the free-text fields relevant to extraction -- description is
    # the real prose; summary is a one-liner; the rest (CVE id, CWE ids,
    # severity) are structured fields useful for cross-referencing into the
    # graph already built, kept alongside for entity alignment later.
    trimmed = [{
        "ghsa_id": a.get("ghsa_id"),
        "cve_id": a.get("cve_id"),
        "summary": a.get("summary", ""),
        "description": a.get("description", ""),
        "severity": a.get("severity"),
        "cwe_ids": [c["cwe_id"] for c in a.get("cwe_ids", [])] if isinstance(a.get("cwe_ids"), list) else [],
        "published_at": a.get("published_at"),
    } for a in all_advisories]

    out_path.write_text(json.dumps(trimmed, indent=2))
    print(f"\nSaved {len(trimmed)} advisories -> {out_path}")
    return out_path


if __name__ == "__main__":
    download_advisories()
