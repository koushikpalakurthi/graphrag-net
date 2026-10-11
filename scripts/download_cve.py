"""
Download CISA Known Exploited Vulnerabilities (KEV) JSON dataset.

CISA KEV provides official CVE records, vulnerability writeups, and CWE mappings
in a structured JSON format accessible over standard HTTPS.
"""
import sys
import json
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import RAW_DIR

CISA_KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"


def download_cve_data():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    target_path = RAW_DIR / "cisa_kev.json"

    print(f"Downloading CISA KEV (CVE database) from {CISA_KEV_URL}...")
    try:
        resp = requests.get(CISA_KEV_URL, timeout=30)
        resp.raise_for_status()
        target_path.write_bytes(resp.content)
        data = resp.json()
        vulnerabilities = data.get("vulnerabilities", [])
        print(f"Successfully saved {len(vulnerabilities)} CVE records to {target_path}")
    except Exception as e:
        print(f"Network error downloading CISA KEV feed: {e}")
        # If network fail, create fallback sample data if missing
        if not target_path.exists():
            fallback_data = {
                "title": "CISA KEV Fallback",
                "vulnerabilities": [
                    {
                        "cveID": "CVE-2023-23397",
                        "vendorProject": "Microsoft",
                        "product": "Outlook",
                        "vulnerabilityName": "Microsoft Outlook Privilege Escalation Vulnerability",
                        "shortDescription": "Microsoft Outlook contains a privilege escalation vulnerability via spoofed NTLM hashes.",
                        "cwes": ["CWE-290"]
                    },
                    {
                        "cveID": "CVE-2023-34362",
                        "vendorProject": "Progress",
                        "product": "MOVEit Transfer",
                        "vulnerabilityName": "Progress MOVEit Transfer SQL Injection Vulnerability",
                        "shortDescription": "Progress MOVEit Transfer contains a SQL injection vulnerability leading to unauthorized access.",
                        "cwes": ["CWE-89"]
                    }
                ]
            }
            target_path.write_text(json.dumps(fallback_data, indent=2))
            print(f"Created fallback CVE data at {target_path}")


if __name__ == "__main__":
    download_cve_data()
