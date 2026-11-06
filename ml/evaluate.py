"""Evaluate the selected checkpoint once its settings have been frozen."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from .common import configure_torch, read_json, write_json
from .metrics import classification_metrics, grouped_bootstrap
from .train import video_arrays


def evaluate_baseline(manifest, run, feature_root, split="val", bootstrap_repeats=300):
    if split not in ("val", "test"):
        raise ValueError("Choose validation or held-out test evaluation.")
    run, feature_root = Path(run), Path(feature_root)
    torch = configure_torch()
    checkpoint = torch.load(run / "model.pt", map_location="cpu", weights_only=True)
    if checkpoint["manifest_fingerprint"] != manifest["fingerprint"]:
        raise ValueError("This checkpoint belongs to a different dataset manifest.")
    metadata = read_json(feature_root / f"{checkpoint['backbone']}.json")
    if metadata["signature"] != checkpoint["feature_signature"]:
        raise ValueError("The cached features do not match the selected model.")
    with np.load(feature_root / f"{checkpoint['backbone']}.npz", allow_pickle=False) as archive:
        cache = {key: archive[key] for key in archive.files}
    mean = checkpoint["scaler_mean"].numpy()
    scale = checkpoint["scaler_scale"].numpy()
    coefficient = checkpoint["head_coefficient"].numpy()
    logits = ((cache["features"] - mean) / scale) @ coefficient + checkpoint["head_intercept"]
    # Stable sigmoid without overflow warnings on extreme scores.
    scores = np.exp(-np.logaddexp(0, -logits))
    ids, labels, video_scores, groups = video_arrays(cache, scores, split)
    threshold = checkpoint["threshold"]
    metrics = classification_metrics(labels, video_scores, threshold)
    requested = [row for row in manifest["rows"] if row["split"] == split]
    usable = set(ids)
    rejected = [row["video_id"] for row in requested if row["video_id"] not in usable]
    report = {
        "model_version": checkpoint["model_version"], "split": split,
        "evaluation_unit": "video", "threshold_source": "validation only",
        "metrics": metrics,
        "coverage": {"requested_videos": len(requested), "analyzed_videos": len(ids),
                     "rejected_videos": len(rejected), "fraction_analyzed": len(ids) / len(requested),
                     "rejected_video_ids": rejected},
        "uncertainty": grouped_bootstrap(labels, video_scores, groups, threshold,
                                         repeats=bootstrap_repeats, seed=manifest["seed"]),
        "interpretation": "Metrics describe analyzable videos in this source-group-held-out sample, not unseen identities or real KYC sessions.",
        "limitations": [manifest["label_limitation"], manifest["identity_limitation"]],
    }
    write_json(run / f"{split}_metrics.json", report)
    with (run / f"{split}_predictions.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["video_id", "source_group", "label", "visual_score", "predicted_label"])
        for video_id, label, score, group in zip(ids, labels, video_scores, groups, strict=True):
            writer.writerow([video_id, group, int(label), float(score), int(score >= threshold)])
    plot_evaluation(labels, video_scores, metrics, run / f"{split}_evaluation.png", split)
    if split == "test":
        training = read_json(run / "training_summary.json")
        training["test_evaluated"] = True
        write_json(run / "training_summary.json", training)
    return report


def plot_evaluation(labels, scores, metrics, output, split):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.metrics import roc_curve

    figure, axes = plt.subplots(1, 2, figsize=(9, 3.8), constrained_layout=True)
    fpr, tpr, _ = roc_curve(labels, scores)
    axes[0].plot(fpr, tpr, color="#245c47", label=f"AUC = {metrics['roc_auc']:.3f}")
    axes[0].plot([0, 1], [0, 1], "--", color="#999999", linewidth=1)
    axes[0].set(xlabel="False positive rate", ylabel="True positive rate", title="Video-level ROC")
    axes[0].legend(loc="lower right")
    matrix = np.asarray(metrics["confusion_matrix"])
    axes[1].imshow(matrix, cmap="Greens")
    for row in range(2):
        for column in range(2):
            axes[1].text(column, row, str(matrix[row, column]), ha="center", va="center",
                         color="white" if matrix[row, column] > matrix.max() / 2 else "#243529", fontsize=14)
    axes[1].set(xticks=[0, 1], yticks=[0, 1], xticklabels=["Real", "Fake"], yticklabels=["Real", "Fake"],
                xlabel="Predicted", ylabel="True label", title="Confusion matrix")
    figure.suptitle(f"DFDC sample · {split} · {metrics['n_videos']} analyzed videos", fontsize=11)
    figure.savefig(output, dpi=180)
    plt.close(figure)
