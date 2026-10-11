"""
Stage 1b: Parse the raw STIX bundle into a normalized node/edge representation
ready for loading into Neo4j (load_neo4j.py) and, later, GNN training (Stage 2).

Design notes:
- Every node keeps its STIX id as a stable primary key (so re-runs are idempotent).
- Every edge carries a `source` field ("mitre_attack") and, where STIX provides
  one, a `confidence` field -- this is the provenance metadata the paper's
  evidence-ranking (Stage 4) and confidence-estimation (Stage 6) stages
  consume later. Inferred edges (added in later ingestion passes, e.g. via
  LLM long-distance relation prediction) will carry source="inferred" so they
  stay distinguishable from directly-sourced ATT&CK edges.
"""
import sys
import json
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import RAW_DIR, PROCESSED_DIR

# STIX type -> our normalized node label
TYPE_MAP = {
    "attack-pattern": "Technique",
    "x-mitre-tactic": "Tactic",
    "intrusion-set": "ThreatGroup",
    "malware": "Software",
    "tool": "Software",
    "course-of-action": "Mitigation",
    "campaign": "Campaign",
    "x-mitre-data-source": "DataSource",
    "x-mitre-data-component": "DataComponent",
    "identity": "Identity",
    "marking-definition": "MarkingDefinition",
}

# STIX relationship-object "relationship_type" -> normalized edge label
REL_TYPE_MAP = {
    "uses": "USES",
    "mitigates": "MITIGATES",
    "subtechnique-of": "SUBTECHNIQUE_OF",
    "detects": "DETECTS",
    "revoked-by": "REVOKED_BY",
    "attributed-to": "ATTRIBUTED_TO",
}


def load_bundle():
    path = RAW_DIR / "enterprise-attack.json"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found -- run download_attack.py first.")
    return json.loads(path.read_text())["objects"]


def extract_nodes(objects):
    nodes = []
    for obj in objects:
        stix_type = obj.get("type")
        label = TYPE_MAP.get(stix_type)
        if label is None:
            continue  # skip relationship objects and types we don't model as nodes
        if obj.get("revoked") or obj.get("x_mitre_deprecated"):
            continue  # skip deprecated/revoked ATT&CK entries

        # ATT&CK external ID (e.g. "T1566", "G0007") -- the human-readable key
        external_id = None
        for ref in obj.get("external_references", []):
            if ref.get("source_name") == "mitre-attack":
                external_id = ref.get("external_id")
                break

        nodes.append({
            "id": obj["id"],                       # stable STIX id, e.g. attack-pattern--...
            "label": label,
            "attack_id": external_id,               # e.g. "T1566"
            "name": obj.get("name", ""),
            "description": obj.get("description", ""),
            "aliases": obj.get("aliases", []),      # for ThreatGroup alias merging in Stage 1c
            "platforms": obj.get("x_mitre_platforms", []),
            "source": "mitre_attack",
        })
    return nodes


def extract_edges(objects):
    edges = []
    skipped_types = Counter()
    for obj in objects:
        if obj.get("type") != "relationship":
            continue
        rel_type = obj.get("relationship_type")
        label = REL_TYPE_MAP.get(rel_type)
        if label is None:
            skipped_types[rel_type] += 1
            continue
        edges.append({
            "source_id": obj["source_ref"],
            "target_id": obj["target_ref"],
            "label": label,
            "description": obj.get("description", ""),
            "source": "mitre_attack",
            "confidence": 1.0,  # directly-sourced ATT&CK edges get full confidence
        })

    # Also synthesize Technique -> Tactic edges from kill_chain_phases,
    # since ATT&CK encodes tactic membership as an attribute, not a relationship object.
    tactic_shortname_to_id = {
        o.get("x_mitre_shortname"): o["id"]
        for o in objects
        if o.get("type") == "x-mitre-tactic"
    }
    for obj in objects:
        if obj.get("type") != "attack-pattern" or obj.get("revoked"):
            continue
        for phase in obj.get("kill_chain_phases", []):
            if phase.get("kill_chain_name") != "mitre-attack":
                continue
            tactic_id = tactic_shortname_to_id.get(phase.get("phase_name"))
            if tactic_id:
                edges.append({
                    "source_id": obj["id"],
                    "target_id": tactic_id,
                    "label": "PART_OF_TACTIC",
                    "description": "",
                    "source": "mitre_attack",
                    "confidence": 1.0,
                })

    if skipped_types:
        print(f"Skipped relationship types not in schema (add to REL_TYPE_MAP if needed): "
              f"{dict(skipped_types)}")
    return edges


def main():
    objects = load_bundle()
    nodes = extract_nodes(objects)
    edges = extract_edges(objects)

    # Only keep edges where both endpoints survived node filtering
    node_ids = {n["id"] for n in nodes}
    edges = [e for e in edges if e["source_id"] in node_ids and e["target_id"] in node_ids]

    (PROCESSED_DIR / "nodes.json").write_text(json.dumps(nodes, indent=2))
    (PROCESSED_DIR / "edges.json").write_text(json.dumps(edges, indent=2))

    label_counts = Counter(n["label"] for n in nodes)
    edge_counts = Counter(e["label"] for e in edges)
    print(f"Nodes: {len(nodes)} total")
    for label, count in label_counts.most_common():
        print(f"  {label}: {count}")
    print(f"Edges: {len(edges)} total")
    for label, count in edge_counts.most_common():
        print(f"  {label}: {count}")
    print(f"\nWrote {PROCESSED_DIR / 'nodes.json'} and {PROCESSED_DIR / 'edges.json'}")


if __name__ == "__main__":
    main()
