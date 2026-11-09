"""Train and select a compact audio baseline using ASVspoof train/dev only."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ml.metrics import classification_metrics, select_threshold
from .dataset import audit_pair, extract_split, load_split, sha256_file
from .features import FEATURE_VERSION


def fit_baseline(train_path, validation_path, output, *, max_groups=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if (output / "model.joblib").exists():
        raise ValueError("This run already has a model. Use a new output directory to avoid overwriting results.")
    audit = audit_pair(train_path, validation_path)
    (output / "dataset_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    features = output / "features"
    full_train = extract_split(train_path, "train", features / "train", audit["train"]["sha256"], max_groups=max_groups)
    full_validation = extract_split(validation_path, "validation", features / "validation", audit["validation"]["sha256"], max_groups=max_groups)
    if not full_train or not full_validation:
        return {"status": "smoke_only", "message": "Partial feature cache created; no model was trained."}
    train = load_split(features / "train", 254)
    validation = load_split(features / "validation", 249)
    if len(train["y"]) != 25380 or len(validation["y"]) != 24844:
        raise ValueError("Extracted feature counts differ from audited dataset counts.")
    if set(train["ids"]) & set(validation["ids"]):
        raise ValueError("Train and validation audio IDs overlap.")
    if set(train["speakers"]) & set(validation["speakers"]):
        raise ValueError("Train and validation speakers overlap.")
    # Equal total weight per class; the challenge data contain many more spoof clips.
    counts = np.bincount(train["y"], minlength=2)
    weights = len(train["y"]) / (2 * counts[train["y"]])
    candidates = [
        ("logistic_c0.1", make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=500))),
        ("logistic_c1", make_pipeline(StandardScaler(), LogisticRegression(C=1, max_iter=500))),
        ("histgb_100", HistGradientBoostingClassifier(max_iter=100, max_leaf_nodes=15,
                                                      learning_rate=0.08, l2_regularization=1.0,
                                                      early_stopping=False, random_state=42)),
    ]
    results = []
    best = None
    for name, estimator in candidates:
        print(f"Fitting {name} on {len(train['y'])} labeled clips...", flush=True)
        if name.startswith("logistic"):
            estimator.fit(train["x"], train["y"], logisticregression__sample_weight=weights)
        else:
            estimator.fit(train["x"], train["y"], sample_weight=weights)
        scores = estimator.predict_proba(validation["x"])[:, 1]
        threshold = select_threshold(validation["y"], scores)
        metrics = classification_metrics(validation["y"], scores, threshold)
        entry = {"candidate": name, "threshold": threshold, "metrics": metrics}
        results.append(entry)
        print(f"{name}: validation balanced accuracy={metrics['balanced_accuracy']:.4f}, "
              f"AUC={metrics['roc_auc']:.4f}", flush=True)
        rank = (metrics["balanced_accuracy"], metrics["roc_auc"])
        if best is None or rank > best[0]:
            best = (rank, name, estimator, threshold, metrics)
    _, selected_name, selected_model, threshold, selected_metrics = best
    model_path = output / "model.joblib"
    joblib.dump({"format_version": 1, "feature_version": FEATURE_VERSION,
                 "estimator": selected_model, "threshold": threshold}, model_path)
    checksum = sha256_file(model_path)
    dataset_fingerprint = hashlib.sha256((audit["train"]["sha256"] + audit["validation"]["sha256"]).encode()).hexdigest()
    summary = {
        "status": "trained", "model_version": f"audio-asv19la-{checksum[:12]}",
        "track": "ASVspoof 2019 LA", "training_type": "CPU log-mel summary classifier",
        "selected_candidate": selected_name, "threshold": float(threshold),
        "feature_version": FEATURE_VERSION, "dataset_fingerprint": dataset_fingerprint,
        "checkpoint_sha256": checksum, "checkpoint_bytes": model_path.stat().st_size,
        "selection_split": "ASVspoof 2019 LA development (Hugging Face validation)",
        "validation_metrics": selected_metrics, "candidate_comparison": results,
        "evaluation_note": "These are model-selection metrics, not held-out test accuracy. No 2019 evaluation or 2021 test audio was used.",
    }
    (output / "training_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
