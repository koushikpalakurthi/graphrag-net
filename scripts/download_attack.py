"""
Stage 1a: Pull MITRE ATT&CK Enterprise data as a STIX 2.1 bundle.

This is a *structured* source (unlike vendor advisories), so it goes straight
into the graph without an LLM extraction pass -- see parse_stix_to_graph.py.
"""
import sys
import json
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import ATTACK_STIX_URL, RAW_DIR


def download_attack_bundle() -> Path:
    out_path = RAW_DIR / "enterprise-attack.json"
    print(f"Fetching MITRE ATT&CK STIX bundle from:\n  {ATTACK_STIX_URL}")
    resp = requests.get(ATTACK_STIX_URL, timeout=60)
    resp.raise_for_status()
    bundle = resp.json()
    out_path.write_text(json.dumps(bundle))
    n_objects = len(bundle.get("objects", []))
    print(f"Saved {n_objects} STIX objects -> {out_path}")
    return out_path


if __name__ == "__main__":
    download_attack_bundle()
