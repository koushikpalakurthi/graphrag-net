"""
Stage 1b (source 3): Parse the CWE catalog into normalized nodes/edges.

Critical design point: parse_capec_to_graph.py already created 336
placeholder Weakness nodes with id="CWE-276" (etc.) whenever a CAPEC attack
pattern referenced a CWE that wasn't loaded yet. load_neo4j.py MERGEs nodes
by id, so as long as this parser emits real Weakness nodes using that exact
same "CWE-<number>" id format, loading this after CAPEC enriches those same
nodes in place (fills in name/description/etc.) rather than creating
duplicates. This is verified in main() below by cross-checking against
capec_nodes.json before writing output.
"""
import sys
import json
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import RAW_DIR, PROCESSED_DIR

# CWE's Related_Weakness "Nature" attribute -> our normalized edge label
NATURE_MAP = {
    "ChildOf": "CHILD_OF",
    "PeerOf": "PEER_OF",
    "CanPrecede": "CAN_PRECEDE",
    "CanAlsoBe": "CAN_ALSO_BE",
    "Requires": "REQUIRES",
    "StartsWith": "STARTS_WITH",
}


def load_catalog():
    path = RAW_DIR / "cwe-archive.json"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found -- run download_cwe.py first.")
    return json.loads(path.read_text())["Weakness_Catalog"]["Weaknesses"]["Weakness"]


def extract_description(w):
    desc = w.get("Description", "")
    ext = w.get("Extended_Description", "")
    if isinstance(ext, dict):
        ext = ext.get("#text", "") if "#text" in ext else ""
    if isinstance(ext, str) and ext:
        return f"{desc} {ext}".strip()
    return desc


def extract_potential_mitigations(w):
    """Flatten Potential_Mitigations into short text -- these feed Stage 5's
    mitigation reasoning as retrievable evidence, not just metadata."""
    pm = w.get("Potential_Mitigations", {}).get("Mitigation")
    if pm is None:
        return []
    items = pm if isinstance(pm, list) else [pm]
    out = []
    for item in items:
        d = item.get("Description", "")
        if isinstance(d, str) and d:
            out.append(d)
    return out


def extract_nodes(weaknesses):
    nodes = []
    for w in weaknesses:
        attr = w["attr"]
        cwe_id = f"CWE-{attr['@_ID']}"   # matches CAPEC placeholder id format exactly
        nodes.append({
            "id": cwe_id,
            "label": "Weakness",
            "attack_id": cwe_id,
            "name": attr.get("@_Name", cwe_id),
            "description": extract_description(w),
            "aliases": [],
            "platforms": [],
            "source": "cwe",
            "abstraction": attr.get("@_Abstraction", ""),
            "status": attr.get("@_Status", ""),
            "mitigations": extract_potential_mitigations(w),
        })
    return nodes


def extract_edges(weaknesses):
    edges = []
    skipped = Counter()
    for w in weaknesses:
        source_id = f"CWE-{w['attr']['@_ID']}"
        rel = w.get("Related_Weaknesses", {}).get("Related_Weakness")
        if rel is None:
            continue
        items = rel if isinstance(rel, list) else [rel]
        for item in items:
            nature = item["attr"]["@_Nature"]
            label = NATURE_MAP.get(nature)
            if label is None:
                skipped[nature] += 1
                continue
            target_id = f"CWE-{item['attr']['@_CWE_ID']}"
            edges.append({
                "source_id": source_id,
                "target_id": target_id,
                "label": label,
                "description": "",
                "source": "cwe",
                "confidence": 1.0,
            })
    if skipped:
        print(f"Skipped relationship natures not in NATURE_MAP: {dict(skipped)}")
    return edges


def main():
    weaknesses = load_catalog()
    nodes = extract_nodes(weaknesses)
    node_ids = {n["id"] for n in nodes}
    edges = extract_edges(weaknesses)
    # Only keep edges where both endpoints exist in this catalog view
    dropped = [e for e in edges if e["source_id"] not in node_ids or e["target_id"] not in node_ids]
    edges = [e for e in edges if e["source_id"] in node_ids and e["target_id"] in node_ids]
    if dropped:
        print(f"Dropped {len(dropped)} edges referencing CWE IDs outside this catalog view "
              f"(e.g. deprecated or out-of-view entries)")

    # Cross-check against CAPEC's placeholder nodes to confirm id-format alignment
    capec_nodes_path = PROCESSED_DIR / "capec_nodes.json"
    if capec_nodes_path.exists():
        capec_nodes = json.loads(capec_nodes_path.read_text())
        placeholder_ids = {n["id"] for n in capec_nodes if n["label"] == "Weakness"}
        overlap = placeholder_ids & node_ids
        print(f"\nCAPEC placeholder Weakness nodes: {len(placeholder_ids)}")
        print(f"Will be enriched by this CWE load (id match): {len(overlap)}")
        still_missing = placeholder_ids - node_ids
        if still_missing:
            print(f"Still unresolved after this load (outside Research Concepts view): "
                  f"{len(still_missing)} -- e.g. {sorted(still_missing)[:5]}")
    else:
        print("\n(capec_nodes.json not found -- run parse_capec_to_graph.py to enable "
              "the placeholder-enrichment cross-check)")

    (PROCESSED_DIR / "cwe_nodes.json").write_text(json.dumps(nodes, indent=2))
    (PROCESSED_DIR / "cwe_edges.json").write_text(json.dumps(edges, indent=2))

    edge_counts = Counter(e["label"] for e in edges)
    print(f"\nCWE nodes: {len(nodes)} total (all :Weakness)")
    print(f"CWE edges: {len(edges)} total")
    for label, count in edge_counts.most_common():
        print(f"  {label}: {count}")
    print(f"\nWrote {PROCESSED_DIR / 'cwe_nodes.json'} and {PROCESSED_DIR / 'cwe_edges.json'}")


if __name__ == "__main__":
    main()
