"""
Feature Extractor for Stage 6 Calibrated Confidence Scoring.

Extracts numeric features across:
1. Retrieval Strength (top score, top margin, graph path density).
2. Cross-Channel Agreement (Jaccard overlap between Text and GNN channels).
3. LLM Consistency & Grounding (sample agreement, unsupported claim ratio).
"""
import re
from typing import Dict, Any, List


def extract_confidence_features(
    query: str,
    evidence_bundle: Dict[str, Any],
    llm_output: Dict[str, Any]
) -> Dict[str, float]:
    """
    Extracts a flat dictionary of numeric features from Stage 3, 4, and 5 outputs.
    """
    entities = evidence_bundle.get("ranked_entities", [])
    triplets = evidence_bundle.get("triplets", [])

    # -------------------------------------------------------------
    # 1. Retrieval Strength Features
    # -------------------------------------------------------------
    scores = [e.get("composite_score", 0.0) for e in entities]
    top1_score = float(scores[0]) if len(scores) > 0 else 0.0
    top2_score = float(scores[1]) if len(scores) > 1 else 0.0
    top1_top2_margin = float(top1_score - top2_score)
    
    n_supporting_paths = float(len(triplets))
    core_links = sum(1 for t in triplets if t.get("is_core_entity_link", False))
    avg_path_length = float(core_links / max(n_supporting_paths, 1.0))

    # -------------------------------------------------------------
    # 2. Cross-Channel Agreement Features
    # -------------------------------------------------------------
    both_count = sum(1 for e in entities if e.get("provenance") == "HYBRID_BOTH")
    text_count = sum(1 for e in entities if e.get("provenance") in ("HYBRID_BOTH", "TEXT_FACTUAL"))
    gnn_count = sum(1 for e in entities if e.get("provenance") in ("HYBRID_BOTH", "GNN_STRUCTURAL"))

    union_count = text_count + gnn_count - both_count
    entity_jaccard = float(both_count / max(union_count, 1))
    evidence_cosine_sim = float(both_count / max(len(entities), 1))
    channels_agree = 1.0 if both_count > 0 else 0.0

    # -------------------------------------------------------------
    # 3. LLM Consistency & Grounding Features
    # -------------------------------------------------------------
    reasoning_text = llm_output.get("reasoning_output", "")
    
    # Self-consistency score passed from Stage 5 or default
    self_consistency_score = float(llm_output.get("self_consistency_score", 0.85))

    # Check for unsupported claims: extract ATT&CK IDs (T1xxx, M1xxx, TA0xxx, S0xxx) and CVEs
    mentioned_ids = set(re.findall(r'\b(?:T\d{4}|M\d{4}|TA\d{4}|S\d{4}|CVE-\d{4}-\d+)\b', reasoning_text, re.IGNORECASE))
    evid_ids = set()
    for e in entities:
        if e.get("attack_id"):
            evid_ids.add(e["attack_id"].upper())
        if e.get("node_id"):
            evid_ids.add(e["node_id"].upper())

    if mentioned_ids:
        unsupported_count = sum(1 for mid in mentioned_ids if mid.upper() not in evid_ids)
        unsupported_claim_ratio = float(unsupported_count / len(mentioned_ids))
    else:
        unsupported_claim_ratio = 0.0

    return {
        "top1_score": round(top1_score, 4),
        "top1_top2_margin": round(top1_top2_margin, 4),
        "n_supporting_paths": round(n_supporting_paths, 4),
        "avg_path_length": round(avg_path_length, 4),
        "entity_jaccard": round(entity_jaccard, 4),
        "evidence_cosine_sim": round(evidence_cosine_sim, 4),
        "channels_agree": round(channels_agree, 4),
        "self_consistency_score": round(self_consistency_score, 4),
        "unsupported_claim_ratio": round(unsupported_claim_ratio, 4)
    }
