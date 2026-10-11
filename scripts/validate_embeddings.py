"""
Stage 2c: Validate that the trained embeddings capture implicit structural
similarity -- entities that are related in behavior/role but NOT directly
connected by an edge. This is the specific claim Stage 2 makes in the paper
("captures structural similarity ... not written explicitly as a graph
edge and is therefore invisible to systems that only traverse the graph
symbolically") so it's the thing worth actually checking, not just training
loss going down.

Method: for a few sample entities, find nearest neighbors by cosine
similarity in embedding space, then check whether the top neighbors share
any DIRECT edge with the query entity. Neighbors with no direct edge are
exactly the "structural similarity invisible to symbolic traversal" the
paper claims -- printed separately from directly-connected neighbors so
this is an honest check, not a self-fulfilling one.
"""
import sys
import json
import pickle
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import PROCESSED_DIR


def load_everything():
    embeddings = pickle.load(open(PROCESSED_DIR / "node_embeddings.pkl", "rb"))

    nodes = {}
    for f in ["nodes.json", "capec_nodes.json", "cwe_nodes.json"]:
        for n in json.loads((PROCESSED_DIR / f).read_text()):
            nodes[n["id"]] = n

    # Build a quick direct-neighbor lookup (undirected) for the "already
    # explicit?" check.
    direct_neighbors = {}
    for f in ["edges.json", "capec_edges.json", "cwe_edges.json"]:
        for e in json.loads((PROCESSED_DIR / f).read_text()):
            direct_neighbors.setdefault(e["source_id"], set()).add(e["target_id"])
            direct_neighbors.setdefault(e["target_id"], set()).add(e["source_id"])

    return embeddings, nodes, direct_neighbors


def nearest_neighbors(query_id, embeddings, nodes, k=8, same_type_only=True):
    if query_id not in embeddings:
        print(f"  [no embedding for {query_id} -- likely an isolated node, see train_gnn.py output]")
        return []

    query_vec = embeddings[query_id]
    query_type = nodes[query_id]["label"]

    candidates = []
    for node_id, vec in embeddings.items():
        if node_id == query_id:
            continue
        if same_type_only and nodes.get(node_id, {}).get("label") != query_type:
            continue
        sim = np.dot(query_vec, vec) / (np.linalg.norm(query_vec) * np.linalg.norm(vec) + 1e-8)
        candidates.append((node_id, sim))

    candidates.sort(key=lambda x: -x[1])
    return candidates[:k]


def report(query_name_hint, query_id, embeddings, nodes, direct_neighbors):
    name = nodes.get(query_id, {}).get("name", query_id)
    print(f"\n=== Nearest neighbors of: {name!r} ({nodes.get(query_id,{}).get('label','?')}) ===")
    neighbors = nearest_neighbors(query_id, embeddings, nodes)
    if not neighbors:
        return

    direct = direct_neighbors.get(query_id, set())
    implicit_count = 0
    for node_id, sim in neighbors:
        n = nodes.get(node_id, {})
        is_direct = node_id in direct
        tag = "[explicit edge]" if is_direct else "[IMPLICIT -- structural only]"
        if not is_direct:
            implicit_count += 1
        print(f"  {sim:.3f}  {n.get('name','?'):<50s} {tag}")

    print(f"  -> {implicit_count}/{len(neighbors)} top neighbors have NO direct edge "
          f"to the query entity (this is the signal Stage 2 is meant to add)")


def main():
    embeddings, nodes, direct_neighbors = load_everything()

    # Pick a few illustrative, well-known entities across different node types.
    name_to_id = {}
    for nid, n in nodes.items():
        name_to_id.setdefault((n["label"], n["name"]), nid)

    samples = [
        ("ThreatGroup", "APT29"),
        ("Technique", "Phishing"),
        ("AttackPattern", "Brute Force"),
        ("Weakness", "Incorrect Default Permissions"),  # CWE-276
    ]

    for label, name in samples:
        key = (label, name)
        if key not in name_to_id:
            print(f"\n(sample entity {label}:{name!r} not found by exact name -- skipping)")
            continue
        report(name, name_to_id[key], embeddings, nodes, direct_neighbors)


if __name__ == "__main__":
    main()
