"""Spoof-positive metrics and development-only robust threshold selection."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import roc_curve

from ml.metrics import classification_metrics


def audio_metrics(labels, scores, threshold):
    metrics = classification_metrics(labels, scores, threshold)
    for old, new in (("n_videos", "n_clips"), ("real_videos", "genuine_clips"), ("fake_videos", "spoof_clips")):
        metrics[new] = metrics.pop(old)
    # Tie-aware ROC interpolation. This is an explicitly named local EER
    # convention, not a claim to reproduce the challenge's discrete DET EER.
    fpr, tpr, _ = roc_curve(labels, scores, drop_intermediate=False)
    fnr = 1 - tpr
    difference = fpr - fnr
    upper = int(np.flatnonzero(difference >= 0)[0])
    if upper == 0 or difference[upper] == 0:
        eer = float((fpr[upper] + fnr[upper]) / 2)
    else:
        lower = upper - 1
        weight = -difference[lower] / (difference[upper] - difference[lower])
        eer = float(fpr[lower] + weight * (fpr[upper] - fpr[lower]))
    metrics["eer"] = eer
    metrics["eer_method"] = "linear interpolation of tie-aware ROC; descriptive, not a deployment threshold"
    return metrics


class NoFeasibleThreshold(ValueError):
    pass


def select_robust_threshold(conditions, max_clean_errors=None):
    """Minimize the largest class error over declared calibration conditions."""
    if not conditions:
        raise ValueError("Calibration conditions are required.")
    for labels, scores in conditions.values():
        audio_metrics(labels, scores, 0.5)  # Reject missing classes/invalid scores.
    thresholds = np.unique(np.concatenate([np.asarray(scores) for _, scores in conditions.values()] + [np.array([0.0, 0.5, 1.0])]))
    errors = []
    for labels, scores in conditions.values():
        labels, scores = np.asarray(labels), np.asarray(scores)
        genuine, spoof = np.sort(scores[labels == 0]), np.sort(scores[labels == 1])
        errors.extend(((len(genuine) - np.searchsorted(genuine, thresholds, side="left")) / len(genuine),
                       np.searchsorted(spoof, thresholds, side="left") / len(spoof)))
    errors = np.stack(errors)
    if max_clean_errors is not None:
        if "clean" not in conditions or len(max_clean_errors) != 2 or any(not 0 <= value <= 1 for value in max_clean_errors):
            raise ValueError("Two valid clean class-error limits are required.")
        index = list(conditions).index("clean") * 2
        feasible = (errors[index] <= max_clean_errors[0]) & (errors[index + 1] <= max_clean_errors[1])
        if not feasible.any():
            raise NoFeasibleThreshold("No calibration threshold satisfies both clean class-error limits.")
        thresholds, errors = thresholds[feasible], errors[:, feasible]
    order = np.lexsort((np.abs(thresholds - 0.5), errors.mean(axis=0), errors.max(axis=0)))
    return float(thresholds[order[0]])


def worst_class_error(conditions):
    return max(max(row["real_flagged_as_fake_rate"], row["fake_accepted_as_real_rate"])
               for row in conditions.values())


def speaker_bootstrap_comparison(labels, old_scores, new_scores, speakers, old_threshold, new_threshold,
                                 repeats=500, seed=20261111):
    """Paired speaker resampling; differences below zero favor the candidate."""
    labels, old_scores, new_scores, speakers = map(np.asarray, (labels, old_scores, new_scores, speakers))
    unique = np.unique(speakers)
    rng = np.random.default_rng(seed)
    differences = {"genuine_false_alarm_rate": [], "missed_spoof_rate": []}
    grouped = [np.flatnonzero(speakers == speaker) for speaker in unique]
    for _ in range(repeats):
        indices = np.concatenate([grouped[i] for i in rng.integers(0, len(unique), len(unique))])
        y = labels[indices]
        if len(np.unique(y)) != 2:
            continue
        old, new = old_scores[indices] >= old_threshold, new_scores[indices] >= new_threshold
        differences["genuine_false_alarm_rate"].append(float(new[y == 0].mean() - old[y == 0].mean()))
        differences["missed_spoof_rate"].append(float((~new[y == 1]).mean() - (~old[y == 1]).mean()))
    return {"method": "paired speaker bootstrap of candidate minus reference error rate",
            "speakers": len(unique), "repeats": repeats,
            "valid_repeats": len(differences["genuine_false_alarm_rate"]),
            "intervals_95": {key: np.percentile(values, [2.5, 97.5]).tolist() if values else None
                             for key, values in differences.items()}}
