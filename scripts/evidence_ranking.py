"""
Stage 4 — Evidence Ranking and Merge Engine for GraphRAG-Net.

Combines, deduplicates, and re-ranks retrieval candidates from Stage 3 (Hybrid Semantic Retriever).
Applies:
1. Dual-Channel Consensus Boost: Multiplies score for entities discovered by both
   Text and GNN channels (HYBRID_BOTH).
2. Source Provenance Weighting: Adjusts scores based on source reliability
   (STIX/CWE/CVE structured data vs LLM extractions vs inferred edges).
3. Subgraph Triplet Extraction: Gathers 1-hop and 2-hop relation triplets connecting top
   entities to construct a unified evidence bundle for downstream LLM reasoning (Stage 5).
"""
import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.hybrid_retrieval import HybridRetriever, NODE_FILES


class EvidenceRanker:
    def __init__(self, retriever: HybridRetriever = None):
        if retriever is None:
            self.retriever = HybridRetriever()
        else:
            self.retriever = retriever

        self.node_source_weights = self._build_source_weight_map()

    def _build_source_weight_map(self) -> Dict[str, float]:
        """Maps node IDs to source reliability weights."""
        weight_map = {}
        for f in NODE_FILES:
            path = self.retriever.PROCESSED_DIR / f if hasattr(self.retriever, "PROCESSED_DIR") else Path("data/processed") / f
            if path.exists():
                data = json.loads(path.read_text())
                if "llm_extracted" in f:
                    w = 0.7
                elif "cve" in f or "capec" in f or "cwe" in f:
                    w = 0.95
                else:
                    w = 1.0  # STIX ATT&CK enterprise data
                for n in data:
                    weight_map[n["id"]] = w
        return weight_map

    def rank_and_merge(
        self,
        query: str,
        top_k: int = 10,
        consensus_boost: float = 1.5
    ) -> Dict[str, Any]:
        """
        Retrieves candidates from Stage 3, applies consensus & provenance weighting,
        deduplicates, and extracts graph relation triplets.
        """
        # Step 1: Fetch initial pool of candidates from Stage 3
        raw_candidates = self.retriever.hybrid_retrieve(query, top_k=top_k * 2)

        # Step 2: Compute composite scores with Consensus Boost & Provenance Weighting
        ranked_items = []
        seen_ids = set()

        for cand in raw_candidates:
            nid = cand["node_id"]
            if nid in seen_ids:
                continue
            seen_ids.add(nid)

            base_rrf = cand["rrf_score"]
            prov = cand["provenance"]

            # Consensus multiplier: Boost nodes confirmed by BOTH channels
            mult = consensus_boost if prov == "HYBRID_BOTH" else 1.0

            # Source provenance weight
            source_weight = self.node_source_weights.get(nid, 0.85)

            composite_score = base_rrf * mult * source_weight

            ranked_items.append({
                "node_id": nid,
                "name": cand["name"],
                "label": cand["label"],
                "attack_id": cand.get("attack_id"),
                "provenance": prov,
                "base_rrf_score": base_rrf,
                "consensus_multiplier": mult,
                "source_weight": source_weight,
                "composite_score": round(composite_score, 5),
                "description": cand.get("description", "")
            })

        # Step 3: Sort by composite score and pick top K
        ranked_items.sort(key=lambda x: x["composite_score"], reverse=True)
        top_entities = ranked_items[:top_k]

        # Step 4: Extract Subgraph Relation Triplets for top entities
        top_entity_ids = {e["node_id"] for e in top_entities}
        triplets = []
        seen_triplets = set()

        for ent in top_entities:
            nid = ent["node_id"]
            neighbors = self.retriever.adj_list.get(nid, [])

            for rel, target_id in neighbors:
                if target_id in self.retriever.id_to_node:
                    target_node = self.retriever.id_to_node[target_id]
                    subj_name = ent["name"]
                    obj_name = target_node.get("name", target_id)

                    triplet_key = (nid, rel, target_id)
                    if triplet_key not in seen_triplets:
                        seen_triplets.add(triplet_key)
                        triplets.append({
                            "subject_id": nid,
                            "subject": subj_name,
                            "relation": rel,
                            "object_id": target_id,
                            "object": obj_name,
                            "is_core_entity_link": target_id in top_entity_ids
                        })

        # Sort triplets so links between top entities appear first
        triplets.sort(key=lambda t: t["is_core_entity_link"], reverse=True)

        return {
            "query": query,
            "ranked_entities": top_entities,
            "triplets": triplets[:25],  # Cap triplets for clean LLM prompt context
            "summary": (
                f"Merged and ranked {len(top_entities)} primary evidence entities "
                f"(Consensus boosted: {sum(1 for e in top_entities if e['provenance'] == 'HYBRID_BOTH')}) "
                f"with {len(triplets[:25])} graph relation triplets."
            )
        }


def main():
    parser = argparse.ArgumentParser(description="Stage 4 Evidence Ranking and Merge for GraphRAG-Net")
    parser.add_argument("--query", type=str, default="APT29 credential access and phishing", help="Analyst query string")
    parser.add_argument("--top-k", type=int, default=8, help="Number of evidence entities to retain")
    args = parser.parse_args()

    ranker = EvidenceRanker()
    bundle = ranker.rank_and_merge(args.query, top_k=args.top_k)

    print("\n=======================================================")
    print(f"STAGE 4 EVIDENCE BUNDLE: {bundle['query']!r}")
    print(f"Summary: {bundle['summary']}")
    print("=======================================================\n")

    print("--- RANKED ENTITIES ---")
    for idx, ent in enumerate(bundle["ranked_entities"], 1):
        print(f"[{idx}] [{ent['provenance']}] {ent['name']} ({ent['label']}) [ID: {ent['attack_id'] or ent['node_id']}]")
        print(f"    Composite Score: {ent['composite_score']} (RRF: {ent['base_rrf_score']} x Consensus: {ent['consensus_multiplier']} x SrcWt: {ent['source_weight']})")
        if ent["description"]:
            print(f"    Snippet: {ent['description'][:150]}...")
        print()

    print(f"--- EXTRACTED GRAPH TRIPLETS ({len(bundle['triplets'])}) ---")
    for idx, trip in enumerate(bundle["triplets"][:10], 1):
        core_flag = " [CORE]" if trip["is_core_entity_link"] else ""
        print(f"  {idx}. ({trip['subject']}) -[:{trip['relation']}]-> ({trip['object']}){core_flag}")


if __name__ == "__main__":
    main()
