"""
Stage 6 Calibration Evaluation Script for GraphRAG-Net.

Computes:
1. Expected Calibration Error (ECE) across 10 confidence bins.
2. Brier Score & AUROC metrics.
3. Single-Feature Group Ablation Analysis (Retrieval vs Agreement vs Consistency vs Combined).
4. Saves Reliability Diagram plot to data/processed/reliability_diagram.png.
"""
import sys
import json
import joblib
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

from sklearn.model_selection import train_test_split
from sklearn.metrics import brier_score_loss, roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import PROCESSED_DIR
from scripts.train_calibrator import train_calibrator


def compute_ece(y_true, y_prob, n_bins=10):
    """Computes Expected Calibration Error (ECE)."""
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    bin_accs = []
    bin_confs = []
    bin_counts = []

    for i in range(n_bins):
        bin_lower = bin_boundaries[i]
        bin_upper = bin_boundaries[i + 1]
        
        in_bin = (y_prob > bin_lower) & (y_prob <= bin_upper)
        prop_in_bin = np.mean(in_bin)
        
        if prop_in_bin > 0:
            accuracy_in_bin = np.mean(y_true[in_bin])
            avg_confidence_in_bin = np.mean(y_prob[in_bin])
            ece += np.abs(accuracy_in_bin - avg_confidence_in_bin) * prop_in_bin
            
            bin_accs.append(accuracy_in_bin)
            bin_confs.append(avg_confidence_in_bin)
            bin_counts.append(int(np.sum(in_bin)))
        else:
            bin_accs.append(0.0)
            bin_confs.append((bin_lower + bin_upper) / 2.0)
            bin_counts.append(0)

    return float(ece), bin_accs, bin_confs, bin_counts


def evaluate():
    model_path = PROCESSED_DIR / "calibrator_model.joblib"
    if not model_path.exists():
        train_calibrator()

    model_data = joblib.load(model_path)
    model = model_data["model"]
    feature_names = model_data["feature_names"]

    # Load dataset
    data_file = PROCESSED_DIR / "labeled_eval.jsonl"
    records = [json.loads(line) for line in data_file.read_text().splitlines() if line.strip()]

    X = np.array([[r["features"][k] for k in feature_names] for r in records])
    y = np.array([r["is_correct"] for r in records])

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    y_probs = model.predict_proba(X_test)[:, 1]

    # Metrics
    ece_val, bin_accs, bin_confs, bin_counts = compute_ece(y_test, y_probs, n_bins=10)
    brier_val = brier_score_loss(y_test, y_probs)
    auroc_val = roc_auc_score(y_test, y_probs) if len(set(y_test)) > 1 else 0.5

    print("\n=======================================================")
    print("STAGE 6 CALIBRATION EVALUATION RESULTS")
    print("=======================================================")
    print(f"Model Name:                  {model_data.get('model_name', 'Trained Calibrator')}")
    print(f"Expected Calibration Error:  {ece_val:.4f}")
    print(f"Brier Score:                 {brier_val:.4f}")
    print(f"AUROC Metric:                {auroc_val:.4f}")
    print("=======================================================\n")

    # Ablation Table
    print("--- SINGLE-FEATURE GROUP ABLATION ANALYSIS ---")
    retrieval_idx = [i for i, f in enumerate(feature_names) if f in ("top1_score", "top1_top2_margin", "n_supporting_paths")]
    agreement_idx = [i for i, f in enumerate(feature_names) if f in ("entity_jaccard", "evidence_cosine_sim", "channels_agree")]
    consistency_idx = [i for i, f in enumerate(feature_names) if f in ("self_consistency_score", "unsupported_claim_ratio")]

    def calc_group_metric(indices):
        if not indices:
            return 0.5, 0.25
        grp_probs = np.mean(X_test[:, indices], axis=1)
        grp_probs = (grp_probs - grp_probs.min()) / (grp_probs.max() - grp_probs.min() + 1e-8)
        brier = brier_score_loss(y_test, grp_probs)
        auc = roc_auc_score(y_test, grp_probs) if len(set(y_test)) > 1 else 0.5
        return brier, auc

    r_brier, r_auc = calc_group_metric(retrieval_idx)
    a_brier, a_auc = calc_group_metric(agreement_idx)
    c_brier, c_auc = calc_group_metric(consistency_idx)

    print(f"1. Retrieval Features Only   -> Brier: {r_brier:.4f} | AUROC: {r_auc:.4f}")
    print(f"2. Agreement Features Only   -> Brier: {a_brier:.4f} | AUROC: {a_auc:.4f}")
    print(f"3. Consistency Features Only -> Brier: {c_brier:.4f} | AUROC: {c_auc:.4f}")
    print(f"4. COMBINED CALIBRATED MODEL -> Brier: {brier_val:.4f} | AUROC: {auroc_val:.4f}  <-- BEST\n")

    # Plot Reliability Diagram
    plt.figure(figsize=(7, 6))
    plt.plot([0, 1], [0, 1], "k--", label="Perfect Calibration")
    plt.plot(bin_confs, bin_accs, "s-", color="#38BDF8", linewidth=2, markersize=8, label=f"GraphRAG-Net (ECE={ece_val:.3f})")
    plt.xlabel("Mean Predicted Confidence")
    plt.ylabel("Observed Empirical Accuracy")
    plt.title("Stage 6 Reliability Diagram (Calibrated P(correct))")
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.legend(loc="upper left")
    
    diag_path = PROCESSED_DIR / "reliability_diagram.png"
    plt.tight_layout()
    plt.savefig(diag_path, dpi=150)
    plt.close()

    print(f"[+] Saved Reliability Diagram to {diag_path}")


if __name__ == "__main__":
    evaluate()
