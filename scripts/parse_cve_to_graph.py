"""
Parse downloaded CVE records (CISA KEV JSON) into normalized nodes and edges.

Emits:
- cve_nodes.json: Vulnerability nodes (id="CVE-2023-XXXX", label="Vulnerability")
- cve_edges.json: Edges connecting CVE Vulnerability nodes to CWE Weakness nodes
"""
import sys
import json
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import RAW_DIR, PROCESSED_DIR


def parse_cve():
    cve_file = RAW_DIR / "cisa_kev.json"
    if not cve_file.exists():
        print(f"{cve_file} not found -- run download_cve.py first.")
        return

    data = json.loads(cve_file.read_text())
    vulnerabilities = data.get("vulnerabilities", [])

    nodes = []
    edges = []

    for item in vulnerabilities:
        cve_id = item.get("cveID")
        if not cve_id:
            continue

        name = item.get("vulnerabilityName") or cve_id
        desc = item.get("shortDescription", "")
        vendor = item.get("vendorProject", "")
        product = item.get("product", "")

        node_id = f"cve--{cve_id}"
        nodes.append({
            "id": node_id,
            "label": "Vulnerability",
            "attack_id": cve_id,
            "name": f"{cve_id}: {name}",
            "description": desc,
            "vendor": vendor,
            "product": product,
            "source": "cisa_kev",
        })

        # Link to CWE Weakness nodes if present
        cwes = item.get("cwes", [])
        for cwe in cwes:
            cwe_str = str(cwe).strip()
            if not cwe_str.startswith("CWE-"):
                cwe_str = f"CWE-{cwe_str}"
            
            # Target CWE node ID format used in parse_cwe_to_graph.py (e.g., "CWE-290")
            edges.append({
                "source_id": node_id,
                "target_id": cwe_str,
                "label": "EXPLOITS_WEAKNESS",
                "description": f"{cve_id} exploits {cwe_str}",
                "source": "cisa_kev",
                "confidence": 1.0,
            })

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    (PROCESSED_DIR / "cve_nodes.json").write_text(json.dumps(nodes, indent=2))
    (PROCESSED_DIR / "cve_edges.json").write_text(json.dumps(edges, indent=2))

    print(f"Parsed {len(nodes)} CVE Vulnerability nodes and {len(edges)} EXPLOITS_WEAKNESS edges.")
    print(f"Wrote {PROCESSED_DIR / 'cve_nodes.json'} and {PROCESSED_DIR / 'cve_edges.json'}")


if __name__ == "__main__":
    parse_cve()
