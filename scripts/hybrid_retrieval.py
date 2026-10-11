"""
Stage 3 — Hybrid Semantic Retrieval Engine for GraphRAG-Net.

Performs parallel retrieval across two complementary channels:
1. Text Retrieval Channel (BM25 + TF-IDF text similarity) -> Factual text matches.
2. Graph-Guided Retrieval Channel (GNN Structural Embeddings) -> Structurally
   analogous & topologically related entities (even without direct text overlap).

Fuses both channels using Reciprocal Rank Fusion (RRF) and attaches 1-hop
subgraph context for downstream GraphRAG generation.
"""
import sys
import json
import pickle
import argparse
from pathlib import Path
from collections import defaultdict

import numpy as np
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import PROCESSED_DIR

NODE_FILES = ["nodes.json", "capec_nodes.json", "cwe_nodes.json", "cve_nodes.json", "llm_extracted_nodes.json"]
EDGE_FILES = ["edges.json", "capec_edges.json", "cwe_edges.json", "cve_edges.json", "llm_extracted_edges.json", "inferred_edges.json"]


class HybridRetriever:
    def __init__(self):
        print("Initializing Stage 3 Hybrid Semantic Retriever...")
        self.nodes = self._load_nodes()
        self.edges, self.adj_list = self._load_edges()
        self.embeddings = self._load_embeddings()
        
        # Build node lookups
        self.id_to_node = {n["id"]: n for n in self.nodes}
        self.node_ids = [n["id"] for n in self.nodes]
        
        # Prepare text corpus for Channel A (BM25 + TF-IDF)
        self.corpus_texts = []
        for n in self.nodes:
            text = f"{n.get('name','')} {n.get('description','')} {' '.join(n.get('aliases',[]))} {n.get('vendor','')} {n.get('product','')}".strip()
            self.corpus_texts.append(text)
            
        print(f"Loaded {len(self.nodes)} nodes, {len(self.edges)} edges, and {len(self.embeddings)} GNN embeddings.")
        
        # Initialize Channel A: BM25 Index
        tokenized_corpus = [text.lower().split() for text in self.corpus_texts]
        self.bm25 = BM25Okapi(tokenized_corpus)
        
        # Initialize Channel A: TF-IDF dense text vectorizer
        self.tfidf = TfidfVectorizer(max_features=5000, stop_words="english")
        self.tfidf_matrix = self.tfidf.fit_transform(self.corpus_texts)

    def _load_nodes(self):
        nodes = []
        seen_ids = set()
        for f in NODE_FILES:
            path = PROCESSED_DIR / f
            if path.exists():
                for n in json.loads(path.read_text()):
                    if n["id"] not in seen_ids:
                        nodes.append(n)
                        seen_ids.add(n["id"])
        return nodes

    def _load_edges(self):
        edges = []
        adj_list = defaultdict(list)
        for f in EDGE_FILES:
            path = PROCESSED_DIR / f
            if path.exists():
                for e in json.loads(path.read_text()):
                    edges.append(e)
                    adj_list[e["source_id"]].append((e["label"], e["target_id"]))
                    adj_list[e["target_id"]].append((f"REV_{e['label']}", e["source_id"]))
        return edges, adj_list

    def _load_embeddings(self):
        path = PROCESSED_DIR / "node_embeddings.pkl"
        if not path.exists():
            raise FileNotFoundError(f"{path} not found -- run train_gnn.py first.")
        return pickle.load(open(path, "rb"))

    def text_retrieval(self, query: str, top_k: int = 20):
        """Channel 1: Factual BM25 + TF-IDF Text Retrieval"""
        query_tokens = query.lower().split()
        bm25_scores = self.bm25.get_scores(query_tokens)
        
        # TF-IDF Cosine similarity
        query_vec = self.tfidf.transform([query])
        tfidf_scores = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
        
        # Combined text score
        combined_text_scores = 0.6 * (bm25_scores / (max(bm25_scores) + 1e-8)) + 0.4 * tfidf_scores
        top_indices = np.argsort(combined_text_scores)[::-1][:top_k]
        
        results = []
        for rank, idx in enumerate(top_indices, 1):
            results.append({
                "node_id": self.node_ids[idx],
                "score": float(combined_text_scores[idx]),
                "rank": rank,
                "channel": "text"
            })
        return results

    def gnn_structural_retrieval(self, seed_node_ids: list, top_k: int = 20):
        """Channel 2: Graph-Guided GNN Structural Retrieval"""
        valid_seeds = [nid for nid in seed_node_ids if nid in self.embeddings]
        if not valid_seeds:
            return []

        # Average seed embedding vector
        seed_vecs = [self.embeddings[nid] for nid in valid_seeds]
        target_vec = np.mean(seed_vecs, axis=0)

        # Compute cosine similarity across all nodes in the GNN vector space
        all_ids = []
        all_vecs = []
        for nid, vec in self.embeddings.items():
            all_ids.append(nid)
            all_vecs.append(vec)

        all_vecs = np.array(all_vecs)
        norm_target = target_vec / (np.linalg.norm(target_vec) + 1e-8)
        norms_all = np.linalg.norm(all_vecs, axis=1, keepdims=True) + 1e-8
        sims = np.dot(all_vecs / norms_all, norm_target)

        top_indices = np.argsort(sims)[::-1][:top_k]
        
        results = []
        for rank, idx in enumerate(top_indices, 1):
            results.append({
                "node_id": all_ids[idx],
                "score": float(sims[idx]),
                "rank": rank,
                "channel": "gnn"
            })
        return results

    def hybrid_retrieve(self, query: str, top_k: int = 10, rrf_k: int = 60):
        """Runs both channels in parallel and merges candidates via Reciprocal Rank Fusion (RRF)"""
        # Step 1: Run Channel A (Text Retrieval)
        text_hits = self.text_retrieval(query, top_k=top_k * 2)
        
        # Step 2: Extract top seed nodes to guide Channel B (GNN Structural Retrieval)
        seed_ids = [hit["node_id"] for hit in text_hits[:5]]
        gnn_hits = self.gnn_structural_retrieval(seed_ids, top_k=top_k * 2)
        
        # Step 3: Reciprocal Rank Fusion (RRF)
        rrf_scores = defaultdict(float)
        channel_provenance = defaultdict(set)
        
        for hit in text_hits:
            nid = hit["node_id"]
            rrf_scores[nid] += 1.0 / (rrf_k + hit["rank"])
            channel_provenance[nid].add("text")
            
        for hit in gnn_hits:
            nid = hit["node_id"]
            rrf_scores[nid] += 1.0 / (rrf_k + hit["rank"])
            channel_provenance[nid].add("gnn")

        # Step 4: Sort by fused RRF score
        sorted_nodes = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        
        fused_results = []
        for rrf_rank, (nid, rrf_score) in enumerate(sorted_nodes, 1):
            node_info = self.id_to_node.get(nid, {"id": nid, "name": nid, "label": "Unknown"})
            prov_set = channel_provenance[nid]
            
            if "text" in prov_set and "gnn" in prov_set:
                prov_label = "HYBRID_BOTH"
            elif "text" in prov_set:
                prov_label = "TEXT_FACTUAL"
            else:
                prov_label = "GNN_STRUCTURAL"

            # Fetch 1-hop subgraph context
            subgraph_neighbors = self.adj_list.get(nid, [])[:5]
            neighbor_summary = [
                f"-[:{rel}]-> {self.id_to_node[target_id]['name']} ({self.id_to_node[target_id]['label']})"
                for rel, target_id in subgraph_neighbors if target_id in self.id_to_node
            ]

            fused_results.append({
                "rrf_rank": rrf_rank,
                "node_id": nid,
                "name": node_info.get("name", ""),
                "label": node_info.get("label", ""),
                "attack_id": node_info.get("attack_id"),
                "provenance": prov_label,
                "rrf_score": round(rrf_score, 5),
                "description": node_info.get("description", "")[:200],
                "subgraph_context": neighbor_summary,
            })

        return fused_results


def main():
    parser = argparse.ArgumentParser(description="Stage 3 Hybrid Semantic Retriever for GraphRAG-Net")
    parser.add_argument("--query", type=str, default="APT29 phishing credential access initial access", help="Analyst query string")
    parser.add_argument("--top-k", type=int, default=8, help="Number of fused results to return")
    args = parser.parse_args()

    retriever = HybridRetriever()
    print(f"\n=======================================================")
    print(f"ANALYST QUERY: {args.query!r}")
    print(f"=======================================================\n")

    results = retriever.hybrid_retrieve(args.query, top_k=args.top_k)

    for res in results:
        print(f"[{res['rrf_rank']}] [{res['provenance']}] {res['name']} ({res['label']}) [ID: {res['attack_id'] or res['node_id']}]")
        print(f"    RRF Score: {res['rrf_score']}")
        if res['description']:
            print(f"    Snippet:   {res['description']}...")
        if res['subgraph_context']:
            print(f"    1-Hop Subgraph Neighbors ({len(res['subgraph_context'])}):")
            for neigh in res['subgraph_context'][:3]:
                print(f"      {neigh}")
        print()


if __name__ == "__main__":
    main()
