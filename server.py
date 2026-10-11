"""
FastAPI Server for GraphRAG-Net Cyber Threat Intelligence Web Interface.

Provides REST API endpoints for:
1. Knowledge Graph statistics & GNN model status.
2. Hybrid Semantic Retrieval (BM25 + GNN cosine similarity).
3. Evidence Ranking & Sub-graph Triplet Extraction.
4. End-to-end GraphRAG CTI Reasoning (Groq LLM / self-test mode).
"""
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scripts.rag_reasoning import RAGReasoningEngine
from config.settings import GROQ_MODEL

app = FastAPI(
    title="GraphRAG-Net CTI API",
    description="Backend API for hybrid GraphRAG cyber threat intelligence reasoning system",
    version="1.0.0"
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize engine instance lazily
_engine_instance: Optional[RAGReasoningEngine] = None

def get_engine() -> RAGReasoningEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = RAGReasoningEngine()
    return _engine_instance


class SearchRequest(BaseModel):
    query: str
    top_k: int = 8
    self_test: bool = False


SAMPLE_QUERIES = [
    {
        "title": "APT29 Credential Access",
        "query": "APT29 credential access and phishing techniques",
        "category": "Threat Actor / TTPs"
    },
    {
        "title": "MOVEit Transfer SQLi",
        "query": "SQL injection vulnerability in Progress MOVEit Transfer",
        "category": "Vulnerability / CVE"
    },
    {
        "title": "Living off the Land",
        "query": "Living off the land techniques and OS credential dumping mitigations",
        "category": "Defense / Mitigations"
    },
    {
        "title": "Spearphishing & Defense Evasion",
        "query": "Spearphishing attachment leading to defense evasion and lateral movement",
        "category": "Attack Chain"
    }
]


@app.get("/api/stats")
def get_stats():
    engine = get_engine()
    retriever = engine.ranker.retriever
    return {
        "status": "online",
        "nodes_count": len(retriever.nodes),
        "edges_count": len(retriever.edges),
        "gnn_embeddings_count": len(retriever.embeddings),
        "model_name": GROQ_MODEL,
        "supported_channels": ["Text Factual (BM25/TF-IDF)", "Graph Structural (GNN Embeddings)"]
    }


@app.get("/api/samples")
def get_samples():
    return {"samples": SAMPLE_QUERIES}


@app.post("/api/search")
def run_search(req: SearchRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query string cannot be empty")
    
    engine = get_engine()
    try:
        res = engine.reason(query=req.query, top_k=req.top_k, self_test=req.self_test)
        
        # Format graph nodes and edges for 2D visualizer (vis-network / D3 format)
        bundle = res["evidence_bundle"]
        nodes_dict = {}
        edges_list = []

        # Color mapping for node types
        type_colors = {
            "Tactic": "#F87171",        # Soft Red
            "Technique": "#FB923C",     # Orange
            "Mitigation": "#34D399",    # Emerald
            "Software": "#38BDF8",      # Cyan
            "Threat Group": "#A78BFA",  # Purple
            "Vulnerability": "#E879F9", # Magenta
            "Weakness": "#FBBF24",      # Amber
            "Pattern": "#F472B6"        # Pink
        }

        # Add top entities to visualization nodes
        for ent in bundle["ranked_entities"]:
            nid = ent["node_id"]
            lbl = ent["label"]
            prov = ent["provenance"]

            border_color = "#38BDF8" if prov == "HYBRID_BOTH" else ("#818CF8" if prov == "GNN_STRUCTURAL" else "#94A3B8")

            nodes_dict[nid] = {
                "id": nid,
                "label": ent["name"],
                "group": lbl,
                "color": type_colors.get(lbl, "#64748B"),
                "provenance": prov,
                "composite_score": ent["composite_score"],
                "attack_id": ent.get("attack_id"),
                "description": ent.get("description", "")
            }

        # Add neighbor targets and edges from triplets
        for trip in bundle["triplets"]:
            s_id = trip["subject_id"]
            o_id = trip["object_id"]
            rel = trip["relation"]

            if o_id not in nodes_dict and o_id in engine.ranker.retriever.id_to_node:
                target_node = engine.ranker.retriever.id_to_node[o_id]
                t_lbl = target_node.get("label", "Unknown")
                nodes_dict[o_id] = {
                    "id": o_id,
                    "label": target_node.get("name", o_id),
                    "group": t_lbl,
                    "color": type_colors.get(t_lbl, "#64748B"),
                    "provenance": "GRAPH_NEIGHBOR",
                    "composite_score": 0.0,
                    "attack_id": target_node.get("attack_id"),
                    "description": target_node.get("description", "")
                }

            edges_list.append({
                "from": s_id,
                "to": o_id,
                "label": rel,
                "is_core": trip["is_core_entity_link"]
            })

        res["graph_data"] = {
            "nodes": list(nodes_dict.values()),
            "edges": edges_list
        }

        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Mount static frontend build if present
dist_path = Path(__file__).resolve().parent / "frontend" / "dist"
if dist_path.exists():
    app.mount("/", StaticFiles(directory=str(dist_path), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    print("Starting GraphRAG-Net FastAPI backend on http://localhost:8000 ...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
