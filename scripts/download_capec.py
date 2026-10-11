"""
Stage 1a (source 2): Pull CAPEC (Common Attack Pattern Enumeration and
Classification) data.

Like ATT&CK, this is a structured source -- no LLM extraction needed. MITRE
publishes it as STIX 2.0 JSON in the same mitre/cti repo that hosts ATT&CK's
STIX 2.0 data, so this reuses the exact same download + parse pattern as
download_attack.py / parse_stix_to_graph.py.
"""
import sys
import json
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import CAPEC_STIX_URL, RAW_DIR


def download_capec_bundle() -> Path:
    out_path = RAW_DIR / "stix-capec.json"
    print(f"Fetching CAPEC STIX bundle from:\n  {CAPEC_STIX_URL}")
    resp = requests.get(CAPEC_STIX_URL, timeout=60)
    resp.raise_for_status()
    bundle = resp.json()
    out_path.write_text(json.dumps(bundle))
    n_objects = len(bundle.get("objects", []))
    print(f"Saved {n_objects} STIX objects -> {out_path}")
    return out_path


if __name__ == "__main__":
    download_capec_bundle()
