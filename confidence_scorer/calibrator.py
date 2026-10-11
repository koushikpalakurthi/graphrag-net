"""
Calibrated Confidence Scorer for Stage 6 of GraphRAG-Net.

Supports:
1. Empirical Calibration Mode (loads trained LogisticRegression / GradientBoosting model).
2. Heuristic Fallback Mode (transparently logs CALIBRATION_STATUS = 'heuristic_unvalidated').
"""
import os
import joblib
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class SubScores(BaseModel):
    retrieval_strength: float = Field(..., description="Quality of text and graph retrieval evidence")
    cross_channel_agreement: float = Field(..., description="Consensus between Text and GNN channels")
    llm_consistency: float = Field(..., description="Self-consistency and grounding of LLM output")


class Stage6Output(BaseModel):
    overall_confidence: float = Field(..., description="Calibrated P(correct) score in [0.0, 1.0]")
    confidence_label: str = Field(..., description="Low (<0.4), Medium (0.4-0.7), or High (>0.7)")
    sub_scores: SubScores
    calibration_status: str = Field(..., description="trained_model or heuristic_unvalidated")
    notes: str = Field(..., description="Auto-generated analyst recommendation note")


class ConfidenceScorer:
    def __init__(self, model_path: Optional[Path] = None):
        if model_path is None:
            model_path = Path("data/processed/calibrator_model.joblib")

        self.model_path = Path(model_path)
        if self.model_path.exists():
            try:
                model_data = joblib.load(self.model_path)
                self.model = model_data.get("model")
                self.feature_names = model_data.get("feature_names", [])
                self.calibration_status = model_data.get("status", "trained_model")
            except Exception as e:
                print(f"[ConfidenceScorer Warning]: Failed loading model ({e}). Using heuristic fallback.")
                self.model = None
                self.calibration_status = "heuristic_unvalidated"
        else:
            self.model = None
            self.calibration_status = "heuristic_unvalidated"

    def score(self, features: Dict[str, float]) -> Stage6Output:
        """
        Computes calibrated confidence score and sub-scores.
        """
        # Calculate normalized sub-scores [0.0 - 1.0]
        retrieval_sub = min(1.0, (features.get("top1_score", 0.0) * 12.0 + features.get("n_supporting_paths", 0) * 0.02) / 2.0)
        retrieval_sub = round(max(0.0, min(1.0, retrieval_sub)), 2)

        agreement_sub = min(1.0, (features.get("entity_jaccard", 0.0) * 0.4 + features.get("evidence_cosine_sim", 0.0) * 0.6) * 1.5)
        agreement_sub = round(max(0.0, min(1.0, agreement_sub)), 2)

        consistency_sub = features.get("self_consistency_score", 0.85) * (1.0 - features.get("unsupported_claim_ratio", 0.0))
        consistency_sub = round(max(0.0, min(1.0, consistency_sub)), 2)

        if self.model is not None:
            # Empirical Trained Model Inference
            try:
                feature_vector = [[features.get(fname, 0.0) for fname in self.feature_names]]
                prob_correct = float(self.model.predict_proba(feature_vector)[0][1])
                overall_conf = round(prob_correct, 2)
            except Exception:
                overall_conf = round(0.4 * retrieval_sub + 0.35 * agreement_sub + 0.25 * consistency_sub, 2)
        else:
            # Heuristic Fallback Mode
            overall_conf = round(0.4 * retrieval_sub + 0.35 * agreement_sub + 0.25 * consistency_sub, 2)

        # Assign confidence label
        if overall_conf >= 0.70:
            label = "High"
        elif overall_conf >= 0.40:
            label = "Medium"
        else:
            label = "Low"

        # Generate analyst weakness note
        sub_dict = {
            "retrieval_strength": retrieval_sub,
            "cross_channel_agreement": agreement_sub,
            "llm_consistency": consistency_sub
        }
        weakest_sub = min(sub_dict, key=sub_dict.get)
        
        notes_map = {
            "retrieval_strength": "Text and graph search returned lower relevance density; verify entity context.",
            "cross_channel_agreement": "Text factual and GNN structural channels partially disagree on entity attribution.",
            "llm_consistency": "LLM response contains potential ungrounded claims or lower sample agreement."
        }
        
        if label == "High" and min(sub_dict.values()) > 0.6:
            notes = "Strong cross-channel consensus between text and GNN structural embeddings."
        else:
            notes = notes_map[weakest_sub]

        return Stage6Output(
            overall_confidence=overall_conf,
            confidence_label=label,
            sub_scores=SubScores(
                retrieval_strength=retrieval_sub,
                cross_channel_agreement=agreement_sub,
                llm_consistency=consistency_sub
            ),
            calibration_status=self.calibration_status,
            notes=notes
        )
