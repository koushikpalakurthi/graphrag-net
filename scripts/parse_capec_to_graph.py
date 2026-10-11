"""
Stage 1b (source 2): Parse the CAPEC STIX bundle into normalized nodes/edges.

Three things this does beyond a straight STIX->graph mapping, because CAPEC's
schema differs from ATT&CK's in useful ways:

1. CAPEC's hierarchy (child_of / parent_of / can_precede) is stored as custom
   attributes on the attack-pattern object itself (x_capec_*_refs), not as
   STIX relationship objects the way ATT&CK models most of its structure --
   so those edges have to be synthesized here, same idea as the
   Technique->Tactic synthesis in parse_stix_to_graph.py.

2. CAPEC attack-patterns carry external_references with source_name="ATTACK"
   pointing at real ATT&CK technique IDs (e.g. "T1574.010"). This is a direct,
   MITRE-authored cross-walk between the two graphs -- we turn it into a
   MAPS_TO_TECHNIQUE edge so a query can walk CAPEC attack pattern -> ATT&CK
   technique -> threat groups that use it, joining both sources in one traversal.

3. CAPEC also references CWE weakness IDs (source_name="cwe") that we don't
   have full data for yet (CWE ingestion isn't built). Rather than dropping
   this information, we create lightweight placeholder CWE nodes with just
   an id/attack_id -- when the CWE parser is built later, its MERGE-by-id
   loader will enrich these same nodes with full data instead of creating
   duplicates.
"""
import sys
import json
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import RAW_DIR, PROCESSED_DIR

TYPE_MAP = {
    "attack-pattern": "AttackPattern",   # distinct label from ATT&CK's "Technique"
    "course-of-action": "Mitigation",    # same label as ATT&CK mitigations -- same concept
}


def load_bundle():
    path = RAW_DIR / "stix-capec.json"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found -- run download_capec.py first.")
    return json.loads(path.read_text())["objects"]


def get_capec_id(obj):
    for ref in obj.get("external_references", []):
        if ref.get("source_name") == "capec":
            return ref.get("external_id")   # e.g. "CAPEC-1"
    return None


def extract_nodes(objects):
    nodes = []
    cwe_placeholder_ids = set()

    for obj in objects:
        stix_type = obj.get("type")
        label = TYPE_MAP.get(stix_type)
        if label is None:
            continue

        node = {
            "id": obj["id"],
            "label": label,
            "attack_id": get_capec_id(obj) if label == "AttackPattern" else None,
            "name": obj.get("name", ""),
            "description": obj.get("description", ""),
            "aliases": [],
            "platforms": obj.get("x_capec_domains", []) if label == "AttackPattern" else [],
            "source": "capec",
        }
        if label == "AttackPattern":
            node["severity"] = obj.get("x_capec_typical_severity", "")
            node["likelihood"] = obj.get("x_capec_likelihood_of_attack", "")
        nodes.append(node)

        # Collect CWE weakness IDs referenced by this attack-pattern for
        # placeholder node creation below.
        if label == "AttackPattern":
            for ref in obj.get("external_references", []):
                if ref.get("source_name") == "cwe":
                    cwe_placeholder_ids.add(ref["external_id"])  # e.g. "CWE-276"

    # Placeholder CWE nodes -- id doubles as attack_id since we have no
    # separate STIX id for them yet. The future CWE loader MERGEs on this
    # same `id` value, so these get enriched in place, not duplicated.
    for cwe_id in cwe_placeholder_ids:
        nodes.append({
            "id": cwe_id,
            "label": "Weakness",
            "attack_id": cwe_id,
            "name": cwe_id,
            "description": "",
            "aliases": [],
            "platforms": [],
            "source": "capec_placeholder",   # distinguishes from a real CWE-sourced node
        })

    return nodes, cwe_placeholder_ids


def extract_edges(objects, cwe_placeholder_ids):
    edges = []

    # (a) Explicit STIX relationship objects -- CAPEC only uses "mitigates"
    for obj in objects:
        if obj.get("type") != "relationship":
            continue
        if obj.get("relationship_type") == "mitigates":
            edges.append({
                "source_id": obj["source_ref"],
                "target_id": obj["target_ref"],
                "label": "MITIGATES",
                "description": obj.get("description", ""),
                "source": "capec",
                "confidence": 1.0,
            })

    # (b) Synthesized edges from x_capec_*_refs attributes on attack-patterns
    ref_field_to_label = {
        "x_capec_child_of_refs": "CHILD_OF",
        "x_capec_can_precede_refs": "CAN_PRECEDE",
    }
    for obj in objects:
        if obj.get("type") != "attack-pattern":
            continue
        for field, label in ref_field_to_label.items():
            for target_id in obj.get(field, []):
                edges.append({
                    "source_id": obj["id"],
                    "target_id": target_id,
                    "label": label,
                    "description": "",
                    "source": "capec",
                    "confidence": 1.0,
                })

        # (c) Cross-source edges: CAPEC -> ATT&CK technique, via MITRE's own
        # external_references cross-walk (source_name="ATTACK").
        for ref in obj.get("external_references", []):
            if ref.get("source_name") == "ATTACK":
                edges.append({
                    "source_id": obj["id"],
                    "target_id": ref["external_id"],   # NOTE: technique attack_id, not STIX id -- resolved below
                    "label": "MAPS_TO_TECHNIQUE",
                    "description": "",
                    "source": "capec",
                    "confidence": 1.0,
                    "target_is_attack_id": True,
                })
            elif ref.get("source_name") == "cwe":
                edges.append({
                    "source_id": obj["id"],
                    "target_id": ref["external_id"],   # "CWE-276" -- matches placeholder node id
                    "label": "EXPLOITS_WEAKNESS",
                    "description": "",
                    "source": "capec",
                    "confidence": 1.0,
                })

    return edges


def resolve_attack_id_targets(edges, existing_attack_nodes_path):
    """
    MAPS_TO_TECHNIQUE edges reference ATT&CK techniques by their attack_id
    (e.g. "T1574.010"), not by STIX id, since that's what CAPEC's cross-walk
    gives us. Resolve those to the actual Technique node STIX ids from the
    already-parsed ATT&CK graph so the edge can be loaded correctly.
    """
    if not existing_attack_nodes_path.exists():
        print("WARNING: ATT&CK nodes.json not found -- run parse_stix_to_graph.py "
              "first if you want MAPS_TO_TECHNIQUE edges resolved. Skipping those edges.")
        return [e for e in edges if not e.get("target_is_attack_id")]

    attack_nodes = json.loads(existing_attack_nodes_path.read_text())
    attack_id_to_stix_id = {
        n["attack_id"]: n["id"] for n in attack_nodes
        if n["label"] == "Technique" and n.get("attack_id")
    }

    resolved = []
    unresolved_count = 0
    for e in edges:
        if not e.get("target_is_attack_id"):
            resolved.append(e)
            continue
        stix_id = attack_id_to_stix_id.get(e["target_id"])
        if stix_id is None:
            unresolved_count += 1
            continue  # technique not in our ATT&CK graph (e.g. deprecated) -- drop the edge
        e = {**e, "target_id": stix_id}
        del e["target_is_attack_id"]
        resolved.append(e)

    if unresolved_count:
        print(f"  {unresolved_count} MAPS_TO_TECHNIQUE edges dropped "
              f"(technique not found in loaded ATT&CK graph)")
    return resolved


def main():
    objects = load_bundle()
    nodes, cwe_placeholder_ids = extract_nodes(objects)
    edges = extract_edges(objects, cwe_placeholder_ids)

    # Resolve MAPS_TO_TECHNIQUE targets against the ATT&CK graph already on disk
    edges = resolve_attack_id_targets(edges, PROCESSED_DIR / "nodes.json")

    # Drop edges whose non-ATT&CK endpoint isn't among our nodes
    node_ids = {n["id"] for n in nodes}
    # MAPS_TO_TECHNIQUE targets are ATT&CK STIX ids, which won't be in our
    # CAPEC node set -- allow those through separately.
    clean_edges = []
    for e in edges:
        if e["label"] == "MAPS_TO_TECHNIQUE":
            if e["source_id"] in node_ids:
                clean_edges.append(e)
        else:
            if e["source_id"] in node_ids and e["target_id"] in node_ids:
                clean_edges.append(e)
    edges = clean_edges

    (PROCESSED_DIR / "capec_nodes.json").write_text(json.dumps(nodes, indent=2))
    (PROCESSED_DIR / "capec_edges.json").write_text(json.dumps(edges, indent=2))

    label_counts = Counter(n["label"] for n in nodes)
    edge_counts = Counter(e["label"] for e in edges)
    print(f"\nCAPEC nodes: {len(nodes)} total")
    for label, count in label_counts.most_common():
        print(f"  {label}: {count}")
    print(f"CAPEC edges: {len(edges)} total")
    for label, count in edge_counts.most_common():
        print(f"  {label}: {count}")
    print(f"\nWrote {PROCESSED_DIR / 'capec_nodes.json'} and {PROCESSED_DIR / 'capec_edges.json'}")


if __name__ == "__main__":
    main()
