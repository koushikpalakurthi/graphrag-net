"""
Stage 1c (unstructured source): Align LLM-extracted entities against the
existing graph, and emit nodes/edges in the same format load_neo4j.py already
consumes.

Three resolution paths per extracted entity, in priority order:
1. known_id_hint matches an existing node's attack_id exactly (e.g. the LLM
   tagged "CWE-787" and CWE-787 is already in the graph) -> direct match,
   no new node created, just new edges pointing at the existing node.
2. Fuzzy name match against existing nodes of the same type, same thresholds
   as resolve_entities.py (>=97 auto, >=88 flagged for review) -> merge if
   confident, otherwise still create a new node but flag the possible
   duplicate for manual review rather than guessing.
3. No match -> genuinely new entity (this is expected and good for things
   like CVE numbers, which aren't in the graph at all yet). Gets a new
   synthetic id so it becomes a real node.

Every edge produced here is tagged source="llm_extracted" with confidence
0.7 (not 1.0 like directly-sourced MITRE data) -- this is what Stage 4's
evidence ranking and Stage 6's confidence estimation are meant to weight
differently from ground-truth structured data, per the paper's design.
"""
import sys
import json
import uuid
from pathlib import Path
from collections import Counter

from rapidfuzz import fuzz

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import PROCESSED_DIR

FUZZY_AUTOMERGE_THRESHOLD = 97
FUZZY_REVIEW_THRESHOLD = 88

LABEL_MAP = {  # extraction entity types -> existing graph node labels
    "ThreatGroup": "ThreatGroup",
    "Technique": "Technique",
    "Software": "Software",
    "Mitigation": "Mitigation",
    "Weakness": "Weakness",
    "AttackPattern": "AttackPattern",
    "Vulnerability": "Vulnerability",  # new label -- CVEs aren't loaded elsewhere yet
    "Campaign": "Campaign",
}


def load_existing_graph():
    nodes = []
    for f in ["nodes.json", "capec_nodes.json", "cwe_nodes.json", "cve_nodes.json"]:
        path = PROCESSED_DIR / f
        if path.exists():
            nodes.extend(json.loads(path.read_text()))
    return nodes


def build_lookup_indexes(existing_nodes):
    by_attack_id = {n["attack_id"]: n for n in existing_nodes if n.get("attack_id")}
    by_type = {}
    for n in existing_nodes:
        by_type.setdefault(n["label"], []).append(n)
    return by_attack_id, by_type


def resolve_entity(entity, by_attack_id, by_type, review_log):
    """Returns (resolved_node_id, is_new_node, new_node_dict_or_None)."""
    label = LABEL_MAP.get(entity["type"])
    if label is None:
        return None, False, None  # unknown type, shouldn't happen given schema filtering

    # Path 1: known_id_hint direct match
    hint = entity.get("known_id_hint")
    if hint and hint in by_attack_id:
        return by_attack_id[hint]["id"], False, None

    # Path 2: fuzzy match against same-type existing nodes
    candidates = by_type.get(label, [])
    best_score, best_node = 0, None
    for n in candidates:
        score = fuzz.token_sort_ratio(entity["name"], n["name"])
        if score > best_score:
            best_score, best_node = score, n

    if best_node and best_score >= FUZZY_AUTOMERGE_THRESHOLD:
        return best_node["id"], False, None

    if best_node and best_score >= FUZZY_REVIEW_THRESHOLD:
        review_log.append({
            "extracted_name": entity["name"], "extracted_type": entity["type"],
            "possible_match": best_node["name"], "possible_match_id": best_node["id"],
            "score": best_score,
        })
        # Still create as new -- don't guess on a borderline match automatically

    # Path 3: genuinely new entity
    new_id = f"llm-extracted--{uuid.uuid4()}"
    new_node = {
        "id": new_id,
        "label": label,
        "attack_id": hint,
        "name": entity["name"],
        "description": "",
        "aliases": [],
        "platforms": [],
        "source": "llm_extracted",
    }
    return new_id, True, new_node


def main():
    triplets_path = PROCESSED_DIR / "llm_extracted_triplets.json"
    if not triplets_path.exists():
        raise FileNotFoundError(f"{triplets_path} not found -- run extract_triplets_llm.py first.")

    extractions = json.loads(triplets_path.read_text())
    existing_nodes = load_existing_graph()
    by_attack_id, by_type = build_lookup_indexes(existing_nodes)

    new_nodes = []
    new_edges = []
    review_log = []
    # name -> resolved id, scoped per-document (extraction batch), since the
    # same string in two different advisories isn't guaranteed to be the same
    # real-world entity without more context than we have here.
    for doc in extractions:
        name_to_id = {}
        for entity in doc["entities"]:
            resolved_id, is_new, new_node = resolve_entity(entity, by_attack_id, by_type, review_log)
            if resolved_id is None:
                continue
            name_to_id[entity["name"]] = resolved_id
            if is_new:
                new_nodes.append(new_node)

        for rel in doc["relations"]:
            src_id = name_to_id.get(rel["source"])
            dst_id = name_to_id.get(rel["target"])
            if src_id is None or dst_id is None:
                continue
            new_edges.append({
                "source_id": src_id,
                "target_id": dst_id,
                "label": rel["relation"],
                "description": f"Extracted from advisory {doc.get('source_id','?')}",
                "source": "llm_extracted",
                "confidence": 0.7,  # lower than structured sources -- see module docstring
            })

    # Deduplicate new nodes (same entity may be "new" across multiple docs
    # within this run since resolution is per-document, not batch-global)
    seen_new_by_name_type = {}
    deduped_nodes = []
    id_remap = {}
    for n in new_nodes:
        key = (n["label"], n["name"].strip().lower())
        if key in seen_new_by_name_type:
            id_remap[n["id"]] = seen_new_by_name_type[key]
            continue
        seen_new_by_name_type[key] = n["id"]
        deduped_nodes.append(n)

    for e in new_edges:
        e["source_id"] = id_remap.get(e["source_id"], e["source_id"])
        e["target_id"] = id_remap.get(e["target_id"], e["target_id"])

    (PROCESSED_DIR / "llm_extracted_nodes.json").write_text(json.dumps(deduped_nodes, indent=2))
    (PROCESSED_DIR / "llm_extracted_edges.json").write_text(json.dumps(new_edges, indent=2))
    (PROCESSED_DIR / "llm_extraction_review_log.json").write_text(json.dumps(review_log, indent=2))

    label_counts = Counter(n["label"] for n in deduped_nodes)
    print(f"New nodes from unstructured extraction: {len(deduped_nodes)}")
    for label, count in label_counts.most_common():
        print(f"  {label}: {count}")
    print(f"New edges: {len(new_edges)}")
    print(f"Flagged for manual review (borderline fuzzy matches): {len(review_log)}")
    print(f"\nWrote llm_extracted_nodes.json, llm_extracted_edges.json, "
          f"llm_extraction_review_log.json")


if __name__ == "__main__":
    main()
