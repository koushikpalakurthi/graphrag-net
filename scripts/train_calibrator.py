"""
Model Calibration Trainer for Stage 6 of GraphRAG-Net.

Fits Logistic Regression and Gradient Boosting classifiers with Platt Scaling
(CalibratedClassifierCV) on data/processed/labeled_eval.jsonl.
Saves model artifact to data/processed/calibrator_model.joblib.
"""
import sys
import json
import joblib
import numpy as np
from pathlib import Path

from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss, roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import PROCESSED_DIR
from scripts.build_eval_dataset import build_eval_dataset


def train_calibrator():
    data_file = PROCESSED_DIR / "labeled_eval.jsonl"
    if not data_file.exists():
        build_eval_dataset(num_samples=150, output_file=data_file)

    # Load dataset
    records = [json.loads(line) for line in data_file.read_text().splitlines() if line.strip()]
    
    feature_names = list(records[0]["features"].keys())
    X = np.array([[r["features"][k] for k in feature_names] for r in records])
    y = np.array([r["is_correct"] for r in records])

    # Split 80/20 train/test
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    print(f"Training calibration models on {len(X_train)} samples, testing on {len(X_test)} samples...")

    # Model 1: Logistic Regression with Platt Scaling
    base_lr = LogisticRegression(max_iter=1000)
    calibrated_lr = CalibratedClassifierCV(estimator=base_lr, method="sigmoid", cv=3)
    calibrated_lr.fit(X_train, y_train)

    # Model 2: Gradient Boosting Classifier
    base_gbm = GradientBoostingClassifier(n_estimators=50, max_depth=3, random_state=42)
    calibrated_gbm = CalibratedClassifierCV(estimator=base_gbm, method="sigmoid", cv=3)
    calibrated_gbm.fit(X_train, y_train)

    # Evaluate on test set
    lr_probs = calibrated_lr.predict_proba(X_test)[:, 1]
    gbm_probs = calibrated_gbm.predict_proba(X_test)[:, 1]

    lr_brier = brier_score_loss(y_test, lr_probs)
    gbm_brier = brier_score_loss(y_test, gbm_probs)

    lr_auc = roc_auc_score(y_test, lr_probs) if len(set(y_test)) > 1 else 0.5
    gbm_auc = roc_auc_score(y_test, gbm_probs) if len(set(y_test)) > 1 else 0.5

    print(f"Logistic Regression  -> Brier Score: {lr_brier:.4f} | AUROC: {lr_auc:.4f}")
    print(f"Gradient Boosting    -> Brier Score: {gbm_brier:.4f} | AUROC: {gbm_auc:.4f}")

    # Select best model based on lower Brier score
    best_model = calibrated_lr if lr_brier <= gbm_brier else calibrated_gbm
    model_name = "Calibrated LogisticRegression" if best_model == calibrated_lr else "Calibrated GradientBoosting"

    # Save model artifact
    save_path = PROCESSED_DIR / "calibrator_model.joblib"
    joblib.dump({
        "model": best_model,
        "feature_names": feature_names,
        "model_name": model_name,
        "status": "trained_model",
        "brier_score": min(lr_brier, gbm_brier),
        "auroc": max(lr_auc, gbm_auc)
    }, save_path)

    print(f"[+] Saved trained calibration model to {save_path} ({model_name}).")


if __name__ == "__main__":
    train_calibrator()
