"""
Stage 1a (source 3): Pull the CWE (Common Weakness Enumeration) catalog.

Structured source, like ATT&CK and CAPEC -- no LLM extraction needed.
"""
import sys
import json
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import CWE_JSON_URL, RAW_DIR


def download_cwe_catalog() -> Path:
    out_path = RAW_DIR / "cwe-archive.json"
    print(f"Fetching CWE catalog from:\n  {CWE_JSON_URL}")
    resp = requests.get(CWE_JSON_URL, timeout=60)
    resp.raise_for_status()
    catalog = resp.json()
    out_path.write_text(json.dumps(catalog))
    n_weaknesses = len(catalog["Weakness_Catalog"]["Weaknesses"]["Weakness"])
    print(f"Saved {n_weaknesses} weaknesses -> {out_path}")
    return out_path


if __name__ == "__main__":
    download_cwe_catalog()
