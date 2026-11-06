"""Video-level metrics and validation-only threshold selection."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    accuracy_score, balanced_accuracy_score, confusion_matrix,
    f1_score, log_loss, precision_score, recall_score, roc_auc_score, roc_curve,
)


def aggregate_scores(video_ids, frame_scores):
    totals = {}
    for video_id, score in zip(video_ids, frame_scores, strict=True):
        totals.setdefault(str(video_id), []).append(float(score))
    return {video_id: float(np.mean(scores)) for video_id, scores in totals.items()}


def select_threshold(labels, scores):
    labels, scores = np.asarray(labels), np.asarray(scores)
    if set(labels.tolist()) != {0, 1}:
        raise ValueError("Validation needs both classes before choosing a threshold.")
    if not np.all(np.isfinite(scores)) or np.any((scores < 0) | (scores > 1)):
        raise ValueError("Scores must be finite values between zero and one.")
    fpr, tpr, thresholds = roc_curve(labels, scores, drop_intermediate=False)
    candidates = [(float((sensitivity + 1 - false_positive) / 2), float(threshold))
                  for false_positive, sensitivity, threshold in zip(fpr, tpr, thresholds, strict=True)
                  if np.isfinite(threshold) and 0 <= threshold <= 1]
    candidates.append((float(balanced_accuracy_score(labels, scores >= 0.5)), 0.5))
    return max(candidates, key=lambda pair: (pair[0], -abs(pair[1] - 0.5)))[1]


def classification_metrics(labels, scores, threshold):
    labels = np.asarray(labels, dtype=int)
    scores = np.asarray(scores, dtype=float)
    if set(labels.tolist()) != {0, 1}:
        raise ValueError("Evaluation requires usable videos from both classes.")
    if not np.all(np.isfinite(scores)) or np.any((scores < 0) | (scores > 1)):
        raise ValueError("Invalid model scores cannot be evaluated.")
    predicted = (scores >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(labels, predicted, labels=[0, 1]).ravel()
    return {
        "n_videos": int(len(labels)), "real_videos": int((labels == 0).sum()),
        "fake_videos": int((labels == 1).sum()), "threshold": float(threshold),
        "accuracy": float(accuracy_score(labels, predicted)),
        "balanced_accuracy": float(balanced_accuracy_score(labels, predicted)),
        "fake_precision": float(precision_score(labels, predicted, zero_division=0)),
        "fake_recall": float(recall_score(labels, predicted, zero_division=0)),
        "fake_f1": float(f1_score(labels, predicted, zero_division=0)),
        "roc_auc": float(roc_auc_score(labels, scores)),
        "log_loss": float(log_loss(labels, scores, labels=[0, 1])),
        "fake_accepted_as_real_rate": float(fn / (fn + tp)),
        "real_flagged_as_fake_rate": float(fp / (fp + tn)),
        "confusion_matrix": [[int(tn), int(fp)], [int(fn), int(tp)]],
        "majority_class_accuracy": float(max((labels == 0).sum(), (labels == 1).sum()) / len(labels)),
        "majority_class_balanced_accuracy": 0.5,
    }


def grouped_bootstrap(labels, scores, groups, threshold, repeats=300, seed=42):
    """Resample source groups together to avoid treating related clips as independent."""
    labels, scores, groups = np.asarray(labels), np.asarray(scores), np.asarray(groups)
    unique = np.unique(groups)
    rng = np.random.default_rng(seed)
    samples = {"balanced_accuracy": [], "roc_auc": []}
    for _ in range(repeats):
        selected = rng.choice(unique, size=len(unique), replace=True)
        indices = np.concatenate([np.flatnonzero(groups == group) for group in selected])
        if len(np.unique(labels[indices])) != 2:
            continue
        samples["balanced_accuracy"].append(balanced_accuracy_score(labels[indices], scores[indices] >= threshold))
        samples["roc_auc"].append(roc_auc_score(labels[indices], scores[indices]))
    return {
        "method": "source-group bootstrap", "requested_repeats": repeats,
        "valid_repeats": len(samples["roc_auc"]),
        "intervals_95": {key: [float(value) for value in np.percentile(values, [2.5, 97.5])] if values else None
                         for key, values in samples.items()},
    }
