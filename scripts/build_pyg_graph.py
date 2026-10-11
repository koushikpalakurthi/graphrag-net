"""
Stage 2a: Build a PyTorch Geometric HeteroData graph from the combined
Stage 1 output (ATT&CK + CAPEC + CWE nodes/edges).

Design notes:
- Reads the same nodes.json/edges.json files that load_neo4j.py loads --
  Neo4j and this script are two independent consumers of the same Stage 1
  output, so there's no dependency on a live Neo4j connection to train.
- Node features are TF-IDF vectors over each node's name+description,
  projected to a fixed dimension per node type. TF-IDF is used instead of a
  pretrained sentence-transformer here because this sandbox can't reach
  huggingface.co -- swapping in real sentence embeddings later is a one-line
  change (replace `build_tfidf_features` with a SentenceTransformer.encode
  call) since the rest of the pipeline only depends on "node id -> vector".
- Every source file's `label` field becomes a PyG node type; every edge
  `label` field becomes a PyG relation type, keyed as
  (src_node_type, relation_label, dst_node_type) per PyG's HeteroData
  convention -- required because MAPS_TO_TECHNIQUE, for instance, always
  goes AttackPattern -> Technique, which PyG needs explicit about.
"""
import sys
import json
import pickle
from pathlib import Path
from collections import defaultdict

import numpy as np
import torch
from torch_geometric.data import HeteroData
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import PROCESSED_DIR

NODE_FILES = ["nodes.json", "capec_nodes.json", "cwe_nodes.json", "cve_nodes.json", "llm_extracted_nodes.json"]
EDGE_FILES = ["edges.json", "capec_edges.json", "cwe_edges.json", "cve_edges.json", "llm_extracted_edges.json", "inferred_edges.json"]

FEATURE_DIM = 128  # per-node embedding dimension after TF-IDF + SVD projection


def load_all_nodes():
    nodes = []
    for f in NODE_FILES:
        path = PROCESSED_DIR / f
        if path.exists():
            nodes.extend(json.loads(path.read_text()))
    return nodes


def load_all_edges():
    edges = []
    for f in EDGE_FILES:
        path = PROCESSED_DIR / f
        if path.exists():
            edges.extend(json.loads(path.read_text()))
    return edges


def build_tfidf_features(nodes):
    """
    TF-IDF over name+description, dimensionality-reduced via SVD to a fixed
    size. Stand-in for pretrained text embeddings (see module docstring).
    Falls back to raw (padded/truncated) TF-IDF for node types too small for
    SVD (e.g. Identity, MarkingDefinition -- single-instance STIX metadata
    types that exist in the schema but aren't graph-relevant entities).
    """
    texts = [f"{n.get('name','')} {n.get('description','')}".strip() or "unknown"
             for n in nodes]
    vectorizer = TfidfVectorizer(max_features=5000, stop_words="english")
    tfidf = vectorizer.fit_transform(texts)

    max_components = min(tfidf.shape[0] - 1, tfidf.shape[1] - 1)
    if max_components < 1:
        # Too few nodes/vocab for SVD -- use raw TF-IDF, padded/truncated to FEATURE_DIM
        dense = tfidf.toarray()
        if dense.shape[1] >= FEATURE_DIM:
            reduced = dense[:, :FEATURE_DIM]
        else:
            pad = np.zeros((dense.shape[0], FEATURE_DIM - dense.shape[1]))
            reduced = np.hstack([dense, pad])
        return reduced.astype(np.float32)

    n_components = min(FEATURE_DIM, max_components)
    svd = TruncatedSVD(n_components=n_components, random_state=42)
    reduced = svd.fit_transform(tfidf)

    # Pad to FEATURE_DIM if SVD gave fewer components (small node-type groups)
    if reduced.shape[1] < FEATURE_DIM:
        pad = np.zeros((reduced.shape[0], FEATURE_DIM - reduced.shape[1]))
        reduced = np.hstack([reduced, pad])

    return reduced.astype(np.float32)


def main():
    nodes = load_all_nodes()
    edges = load_all_edges()
    print(f"Loaded {len(nodes)} nodes, {len(edges)} edges from Stage 1 output")

    # Group nodes by type, build id -> (type, local_index) lookup
    nodes_by_type = defaultdict(list)
    id_to_type_idx = {}
    for n in nodes:
        t = n["label"]
        idx = len(nodes_by_type[t])
        nodes_by_type[t].append(n)
        id_to_type_idx[n["id"]] = (t, idx)

    data = HeteroData()

    # --- Node features, per type ---
    id_index_maps = {}  # node_type -> {stix_id: local_idx}, saved for later use
    for node_type, type_nodes in nodes_by_type.items():
        features = build_tfidf_features(type_nodes)
        data[node_type].x = torch.tensor(features, dtype=torch.float)
        data[node_type].node_ids = [n["id"] for n in type_nodes]  # for de-indexing later
        id_index_maps[node_type] = {n["id"]: i for i, n in enumerate(type_nodes)}
        print(f"  :{node_type}  {len(type_nodes)} nodes, feature dim {features.shape[1]}")

    # --- Edges, grouped by (src_type, relation, dst_type) ---
    edge_groups = defaultdict(list)
    dropped = 0
    for e in edges:
        src_info = id_to_type_idx.get(e["source_id"])
        dst_info = id_to_type_idx.get(e["target_id"])
        if src_info is None or dst_info is None:
            dropped += 1
            continue
        src_type, src_idx = src_info
        dst_type, dst_idx = dst_info
        key = (src_type, e["label"], dst_type)
        edge_groups[key].append((src_idx, dst_idx))

    for (src_type, rel, dst_type), pairs in edge_groups.items():
        arr = np.array(pairs, dtype=np.int64).T  # shape [2, num_edges]
        data[src_type, rel, dst_type].edge_index = torch.tensor(arr, dtype=torch.long)
        print(f"  ({src_type})-[{rel}]->({dst_type})  {len(pairs)} edges")

    if dropped:
        print(f"\nDropped {dropped} edges with an endpoint not present in loaded nodes")

    # Save both the HeteroData object and the id<->index maps (needed to map
    # trained embeddings back to real entity ids in Stage 2c validation).
    out_path = PROCESSED_DIR / "hetero_graph.pt"
    torch.save(data, out_path)
    with open(PROCESSED_DIR / "id_index_maps.pkl", "wb") as f:
        pickle.dump(id_index_maps, f)

    print(f"\nSaved HeteroData -> {out_path}")
    print(f"Saved id/index maps -> {PROCESSED_DIR / 'id_index_maps.pkl'}")
    print(f"\nGraph summary: {data}")


if __name__ == "__main__":
    main()
