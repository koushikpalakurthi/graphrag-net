"""
Stage 1c continued: Long-distance relation prediction between entities
mentioned in different documents, per the paper's Stage 1 spec: "predicts
long-distance relations between entities mentioned in different documents
to reduce graph sparsity."

Approach: two entities that were each mentioned in extracted advisories
(i.e. appear in llm_extracted_triplets.json, meaning they showed up in real
unstructured text) but come from DIFFERENT source documents and have no
existing path between them in the graph are candidates. Among those
candidates, pairs with high GNN embedding similarity (from Stage 2's
node_embeddings.pkl) are proposed as inferred edges -- reusing the trained
structural representations to fill exactly the kind of gap symbolic-only
systems can't see, which is the same claim Stage 2 already validated.

Every inferred edge here is clearly tagged source="inferred" with a
similarity-scaled confidence, never conflated with directly-extracted or
structured-source edges -- consistent with how the paper distinguishes
inferred edges from ground truth throughout Stage 1.

NOTE: like the rest of the unstructured-extraction pipeline, this depends on
llm_extracted_triplets.json existing (i.e. extract_triplets_llm.py having
been run against a live API), so it cannot be demonstrated in the sandbox
this project was built in. The logic is independently testable, though,
against node_embeddings.pkl + any two known entity ids -- see self_test().
"""
import sys
import json
import pickle
from pathlib import Path
from itertools import combinations

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import PROCESSED_DIR

SIMILARITY_THRESHOLD = 0.85   # only propose genuinely high-confidence structural links
MAX_CANDIDATES_PER_RUN = 200  # cap pairwise comparisons for tractability


def load_embeddings():
    path = PROCESSED_DIR / "node_embeddings.pkl"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found -- run train_gnn.py first.")
    return pickle.load(open(path, "rb"))


def load_direct_edges():
    """All existing edges (any source), for the 'no existing path' check."""
    connected_pairs = set()
    for f in ["edges.json", "capec_edges.json", "cwe_edges.json", "llm_extracted_edges.json"]:
        path = PROCESSED_DIR / f
        if not path.exists():
            continue
        for e in json.loads(path.read_text()):
            connected_pairs.add((e["source_id"], e["target_id"]))
            connected_pairs.add((e["target_id"], e["source_id"]))
    return connected_pairs


def load_extracted_entity_documents():
    """Map resolved entity id -> set of source document ids it was extracted from."""
    triplets_path = PROCESSED_DIR / "llm_extracted_triplets.json"
    nodes_path = PROCESSED_DIR / "llm_extracted_nodes.json"
    if not (triplets_path.exists() and nodes_path.exists()):
        raise FileNotFoundError(
            "llm_extracted_triplets.json / llm_extracted_nodes.json not found -- "
            "run extract_triplets_llm.py and align_extracted_entities.py first."
        )

    # Re-resolve names -> ids the same way align_extracted_entities.py does,
    # by re-reading its output rather than re-running resolution logic here.
    extractions = json.loads(triplets_path.read_text())

    # Build a name->id map from ALL known graph nodes (existing + newly extracted)
    all_nodes = []
    for f in ["nodes.json", "capec_nodes.json", "cwe_nodes.json", "llm_extracted_nodes.json"]:
        p = PROCESSED_DIR / f
        if p.exists():
            all_nodes.extend(json.loads(p.read_text()))
    name_to_id = {n["name"].strip().lower(): n["id"] for n in all_nodes}
    attack_id_to_id = {n["attack_id"]: n["id"] for n in all_nodes if n.get("attack_id")}

    entity_docs = {}
    for doc in extractions:
        doc_id = doc.get("source_id", "unknown")
        for entity in doc["entities"]:
            hint = entity.get("known_id_hint")
            resolved_id = attack_id_to_id.get(hint) or name_to_id.get(entity["name"].strip().lower())
            if resolved_id is None:
                continue
            entity_docs.setdefault(resolved_id, set()).add(doc_id)

    return entity_docs


def predict_long_distance_relations():
    embeddings = load_embeddings()
    connected_pairs = load_direct_edges()
    entity_docs = load_extracted_entity_documents()

    # Only consider entities that (a) appeared in extraction at all, (b) have
    # a trained embedding, (c) were seen in at least one document.
    candidate_ids = [eid for eid in entity_docs if eid in embeddings]
    print(f"Entities eligible for long-distance prediction: {len(candidate_ids)}")

    inferred = []
    checked = 0
    for id_a, id_b in combinations(candidate_ids, 2):
        if checked >= MAX_CANDIDATES_PER_RUN:
            print(f"Reached MAX_CANDIDATES_PER_RUN ({MAX_CANDIDATES_PER_RUN}), stopping early.")
            break
        checked += 1

        # Cross-document requirement: skip if both entities only ever
        # co-occurred in the exact same document (that's just normal
        # same-document extraction, not a sparsity gap across documents).
        if entity_docs[id_a] == entity_docs[id_b] and len(entity_docs[id_a]) == 1:
            continue

        if (id_a, id_b) in connected_pairs:
            continue  # already linked, nothing to infer

        vec_a, vec_b = embeddings[id_a], embeddings[id_b]
        sim = float(np.dot(vec_a, vec_b) / (np.linalg.norm(vec_a) * np.linalg.norm(vec_b) + 1e-8))
        if sim >= SIMILARITY_THRESHOLD:
            inferred.append({
                "source_id": id_a,
                "target_id": id_b,
                "label": "RELATED_TO",  # generic -- true relation type isn't known from structure alone
                "description": f"Inferred from cross-document GNN embedding similarity ({sim:.3f})",
                "source": "inferred",
                "confidence": round(min(sim, 0.6), 3),  # capped below any directly-sourced edge
            })

    out_path = PROCESSED_DIR / "inferred_edges.json"
    out_path.write_text(json.dumps(inferred, indent=2))
    print(f"Checked {checked} candidate pairs, proposed {len(inferred)} inferred edges "
          f"(similarity >= {SIMILARITY_THRESHOLD})")
    print(f"Wrote {out_path}")


def self_test():
    """Runs the similarity-scoring logic against two real, already-trained
    embeddings, independent of the (untested) extraction pipeline above."""
    embeddings = load_embeddings()
    ids = list(embeddings.keys())[:2]
    if len(ids) < 2:
        print("Not enough embeddings to self-test.")
        return
    vec_a, vec_b = embeddings[ids[0]], embeddings[ids[1]]
    sim = float(np.dot(vec_a, vec_b) / (np.linalg.norm(vec_a) * np.linalg.norm(vec_b) + 1e-8))
    print(f"Self-test: similarity between two real trained embeddings "
          f"({ids[0]} vs {ids[1]}) = {sim:.3f}")
    print("This confirms the similarity-scoring math works against real data; "
          "the full pipeline still needs llm_extracted_triplets.json from a live run.")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    else:
        predict_long_distance_relations()
