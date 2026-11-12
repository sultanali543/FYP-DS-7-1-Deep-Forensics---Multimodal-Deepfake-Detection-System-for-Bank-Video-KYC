"""A bounded CPU experiment with declared candidates and separate dev speakers.

No evaluation/test samples are used here. Augmented views stay with their source.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import time

import joblib
import numpy as np
import pyarrow.parquet as pq
import soundfile as sf
from sklearn.ensemble import HistGradientBoostingClassifier
from threadpoolctl import threadpool_limits

from .augmentation import PROFILES, VERSION, channel_batch
from .dataset import COLUMNS, audit_pair, extract_split, load_split, sha256_file
from .features import FEATURE_VERSION, SAMPLE_RATE, waveform_features
from .metrics import NoFeasibleThreshold, audio_metrics, select_robust_threshold, speaker_bootstrap_comparison, worst_class_error
from .predict import load_model

SEED = 20261111
CANDIDATES = (("clean_histgb200_l15", False, 15), ("aug_histgb200_l15", True, 15),
              ("aug_histgb200_l31", True, 31))


def write_json(path, value):
    temporary = Path(path).with_suffix(".tmp.json")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def balanced_ids(metadata, per_class, seed):
    """Round-robin speaker/attack strata, with deterministic random order within."""
    if per_class < 1:
        raise ValueError("Sample counts must be positive.")
    rng = np.random.default_rng(seed)
    selected = []
    for label in (0, 1):
        buckets = {}
        for row in metadata:
            if int(row["key"]) == label:
                buckets.setdefault((row["speaker_id"], row["system_id"]), []).append(row["audio_file_name"])
        if sum(map(len, buckets.values())) < per_class:
            raise ValueError("Requested more distinct utterances than available in a class.")
        buckets = [list(rng.permutation(sorted(buckets[key]))) for key in sorted(buckets)]
        chosen = []
        while len(chosen) < per_class:
            for bucket in buckets:
                if bucket and len(chosen) < per_class:
                    chosen.append(str(bucket.pop()))
        selected.extend(chosen)
    return sorted(selected)


def split_dev_speakers(speakers, seed=SEED):
    speakers = np.random.default_rng(seed).permutation(sorted(set(speakers)))
    if len(speakers) < 4:
        raise ValueError("Need at least four development speakers for disjoint selection.")
    middle = len(speakers) // 2
    return sorted(speakers[:middle].tolist()), sorted(speakers[middle:].tolist())


def condition_weights(labels, conditions):
    """Equal total mass for each class within each channel condition."""
    labels, conditions = np.asarray(labels), np.asarray(conditions)
    unique = np.unique(conditions)
    weights = np.zeros(len(labels), dtype=np.float64)
    for condition in unique:
        for label in (0, 1):
            mask = (conditions == condition) & (labels == label)
            if not mask.any():
                raise ValueError("Every training condition needs both classes.")
            weights[mask] = len(labels) / (len(unique) * 2 * mask.sum())
    return weights


def extract_channel_cache(path, selected_ids, cache, identity, *, threads=2, max_groups=None):
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    scratch = cache / "scratch"
    scratch.mkdir(exist_ok=True)
    marker = cache / "identity.json"
    if marker.exists() and json.loads(marker.read_text()) != identity:
        raise ValueError("Augmentation cache belongs to another experiment.")
    write_json(marker, identity)
    selected = set(selected_ids)
    parquet = pq.ParquetFile(path)
    processed = 0
    started = time.monotonic()

    def decode(row):
        name = row["audio_file_name"]
        if row["audio"]["path"] != name + ".flac":
            raise ValueError("Embedded audio filename mismatch.")
        waveform, rate = sf.read(io.BytesIO(row["audio"]["bytes"]), dtype="float32")
        if rate != SAMPLE_RATE or waveform.ndim != 1:
            raise ValueError("Training audio must be mono at 16 kHz.")
        return name, waveform

    with ThreadPoolExecutor(max_workers=threads) as executor, threadpool_limits(limits=1):
        for group in range(parquet.num_row_groups):
            metadata = parquet.read_row_group(group, columns=["audio_file_name"])["audio_file_name"].to_pylist()
            if not selected.intersection(metadata):
                continue
            if max_groups is not None and processed >= max_groups:
                return False
            processed += 1
            target = cache / f"group-{group:04d}.npz"
            if not target.exists():
                rows = [row for row in parquet.read_row_group(group).to_pylist() if row["audio_file_name"] in selected]
                items = [decode(row) for row in rows]

                def convert_profile(profile):
                    views = channel_batch(items, profile, seed=SEED, scratch=scratch)
                    return [(waveform_features(view, SAMPLE_RATE), int(row["key"]), row["audio_file_name"],
                             row["speaker_id"], row["system_id"], profile)
                            for row, view in zip(rows, views, strict=True)]

                values = [item for batch in executor.map(convert_profile, PROFILES) for item in batch]
                temporary = target.with_suffix(".tmp.npz")
                np.savez_compressed(temporary, x=np.stack([item[0] for item in values]),
                                    **{key: np.asarray([item[index] for item in values])
                                       for index, key in enumerate(("y", "ids", "speakers", "systems", "conditions"), 1)})
                temporary.replace(target)
            if processed % 10 == 0 or max_groups is not None:
                print(f"{cache.name}: {processed} selected row groups; {time.monotonic() - started:.1f}s", flush=True)
    return True


def load_channels(cache, selected_ids):
    arrays = {key: [] for key in ("x", "y", "ids", "speakers", "systems", "conditions")}
    for file in sorted(Path(cache).glob("group-*.npz")):
        with np.load(file, allow_pickle=False) as values:
            for key in arrays:
                arrays[key].append(values[key])
    if not arrays["x"]:
        raise ValueError("No channel features found.")
    result = {key: np.concatenate(values) for key, values in arrays.items()}
    expected = {(name, profile) for name in selected_ids for profile in PROFILES}
    pairs = list(zip(result["ids"].tolist(), result["conditions"].tolist(), strict=True))
    if len(pairs) != len(set(pairs)) or set(pairs) != expected:
        raise ValueError("Augmented cache is incomplete or contains duplicate/unexpected views.")
    if not np.isfinite(result["x"]).all():
        raise ValueError("Invalid augmented feature values.")
    return result


def _condition_data(clean, augmented, speakers):
    result = {}
    for name, values in (("clean", clean), *((profile, augmented) for profile in PROFILES)):
        mask = np.isin(values["speakers"], speakers)
        if name != "clean":
            mask &= values["conditions"] == name
        result[name] = {key: value[mask] for key, value in values.items()}
        if set(result[name]["y"].tolist()) != {0, 1}:
            raise ValueError("Every development role/condition must contain both classes.")
    return result


def fit_robustness(train_path, validation_path, baseline_run, output, *, train_per_class=1000,
                   dev_per_class=800, threads=2, max_groups=None, constrained=False, reuse_channels=None):
    if not 1 <= threads <= 4:
        raise ValueError("Use one to four CPU threads.")
    if max_groups is not None and (max_groups < 1 or reuse_channels is not None):
        raise ValueError("Use a positive max-groups only for fresh extraction checks, without reuse-channels.")
    output, baseline_run = Path(output), Path(baseline_run)
    if output.resolve() == baseline_run.resolve():
        raise ValueError("The reference run must not be overwritten.")
    output.mkdir(parents=True, exist_ok=True)
    if (output / "model.joblib").exists():
        raise ValueError("This run is finished. Choose a new output directory.")
    audit = audit_pair(train_path, validation_path)
    reference_summary, reference = load_model(baseline_run)
    original_audit = json.loads((baseline_run / "dataset_audit.json").read_text())
    for split in ("train", "validation"):
        if original_audit[split]["sha256"] != audit[split]["sha256"]:
            raise ValueError("Reference and experiment datasets differ.")
    metadata = {split: pq.ParquetFile(path).read(columns=COLUMNS).to_pylist()
                for split, path in (("train", train_path), ("validation", validation_path))}
    if {row["audio_file_name"] for row in metadata["train"]} & {row["audio_file_name"] for row in metadata["validation"]}:
        raise ValueError("Train/development audio IDs overlap.")
    calibration, selection = split_dev_speakers(audit["validation"]["speakers"])
    selections = {"train": balanced_ids(metadata["train"], train_per_class, SEED),
                  "validation": balanced_ids(metadata["validation"], dev_per_class, SEED + 1)}
    from imageio_ffmpeg import get_ffmpeg_exe
    candidates = CANDIDATES[-1:] if constrained else CANDIDATES
    plan = {"experiment_version": 2 if constrained else 1, "seed": SEED, "feature_version": FEATURE_VERSION,
            "augmentation_version": VERSION, "profiles": list(PROFILES),
            "ffmpeg_sha256": sha256_file(get_ffmpeg_exe()), "reference_sha256": reference_summary["checkpoint_sha256"],
            "source_sha256": {split: audit[split]["sha256"] for split in selections},
            "augmented_ids": selections, "calibration_speakers": calibration, "selection_speakers": selection,
            "candidates": [list(row) for row in candidates], "iterations": 200, "learning_rate": 0.06,
            "l2_regularization": 3.0, "threshold_rule": "minimize worst class error across calibration conditions",
            "selection_rule": "minimize worst class error on selection speakers; clean class errors may increase by at most 0.01 versus reference",
            "evaluation_status": "development only; no independent test data"}
    if constrained:
        plan["threshold_rule"] += "; enforce reference calibration clean FPR/FNR plus 0.01 limits"
        plan["blend_candidate_weights"] = [0.25, 0.5]
    plan_path = output / "experiment_plan.json"
    if plan_path.exists() and json.loads(plan_path.read_text()) != plan:
        raise ValueError("Run configuration changed. Start a new output directory.")
    write_json(plan_path, plan)
    write_json(output / "dataset_audit.json", audit)
    identity = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    clean = {}
    for split, path in (("train", train_path), ("validation", validation_path)):
        cache = baseline_run / "features" / split
        expected_identity = {"source_sha256": audit[split]["sha256"], "feature_version": FEATURE_VERSION}
        if not (cache / "identity.json").exists():
            cache = output / "clean_features" / split
            extract_split(path, split, cache, audit[split]["sha256"])
        if json.loads((cache / "identity.json").read_text()) != expected_identity:
            raise ValueError("Clean feature cache has incompatible provenance.")
        clean[split] = load_split(cache, pq.ParquetFile(path).num_row_groups)
        rows = metadata[split]
        for key, column in (("ids", "audio_file_name"), ("y", "key"), ("speakers", "speaker_id"), ("systems", "system_id")):
            if clean[split][key].tolist() != [row[column] for row in rows]:
                raise ValueError("Clean feature metadata does not match the audited source.")
    channel_root = Path(reuse_channels) if reuse_channels else output
    if reuse_channels:
        previous = json.loads((channel_root / "experiment_plan.json").read_text())
        for key in ("seed", "feature_version", "augmentation_version", "profiles", "ffmpeg_sha256", "source_sha256", "augmented_ids"):
            if previous[key] != plan[key]:
                raise ValueError("Reused channel cache has incompatible preprocessing or sources.")
        previous_hash = hashlib.sha256(json.dumps(previous, sort_keys=True).encode()).hexdigest()
        for split in selections:
            if json.loads((channel_root / f"channels_{split}/identity.json").read_text()) != {"plan_sha256": previous_hash, "split": split}:
                raise ValueError("Reused cache identity does not match its experiment plan.")
    else:
        complete = True
        for split, path in (("train", train_path), ("validation", validation_path)):
            done = extract_channel_cache(path, selections[split], output / f"channels_{split}",
                                         {"plan_sha256": identity, "split": split}, threads=threads, max_groups=max_groups)
            complete = complete and done
        if not complete:
            return {"status": "smoke_only", "message": "Partial channel cache only; no candidate trained."}
    augmented = {split: load_channels(channel_root / f"channels_{split}", selections[split]) for split in selections}
    calibration_data = _condition_data(clean["validation"], augmented["validation"], calibration)
    selection_data = _condition_data(clean["validation"], augmented["validation"], selection)
    comparisons, models, predictions = [], {}, {}
    clean_limits = None
    if constrained:
        with threadpool_limits(limits=threads):
            clean_reference = audio_metrics(calibration_data["clean"]["y"],
                reference["estimator"].predict_proba(calibration_data["clean"]["x"])[:, 1], reference["threshold"])
        clean_limits = tuple(min(1.0, clean_reference[key] + 0.01)
                             for key in ("real_flagged_as_fake_rate", "fake_accepted_as_real_rate"))

    def compare(name, estimator, threshold=None):
        feasible = True
        with threadpool_limits(limits=threads):
            if threshold is None:
                scores = {condition: (values["y"], estimator.predict_proba(values["x"])[:, 1])
                          for condition, values in calibration_data.items()}
                try:
                    threshold = select_robust_threshold(scores, clean_limits)
                except NoFeasibleThreshold:
                    threshold, feasible = reference["threshold"], False
            predictions[name] = {condition: estimator.predict_proba(values["x"])[:, 1]
                                 for condition, values in selection_data.items()}
        metrics = {condition: audio_metrics(values["y"], predictions[name][condition], threshold)
                   for condition, values in selection_data.items()}
        row = {"candidate": name, "threshold": float(threshold), "selection_metrics": metrics,
               "worst_class_error": worst_class_error(metrics), "calibration_feasible": feasible}
        if comparisons:
            base = comparisons[0]["selection_metrics"]["clean"]
            row["passes_clean_guard"] = feasible and all(metrics["clean"][key] <= base[key] + 0.01
                                            for key in ("real_flagged_as_fake_rate", "fake_accepted_as_real_rate"))
        else:
            row["passes_clean_guard"] = True
        comparisons.append(row)
        models[name] = estimator
        candidate_dir = output / "candidate_models"
        candidate_dir.mkdir(exist_ok=True)
        joblib.dump(estimator, candidate_dir / f"{name}.joblib")
        print(json.dumps({key: row[key] for key in ("candidate", "threshold", "worst_class_error", "passes_clean_guard")}), flush=True)
        write_json(output / "candidate_progress.json", comparisons)

    compare("reference_fixed", reference["estimator"], float(reference["threshold"]))
    compare("reference_rethresholded", reference["estimator"])
    for name, use_augmentation, leaves in candidates:
        x, y = clean["train"]["x"], clean["train"]["y"]
        conditions = np.full(len(y), "clean", dtype="U20")
        if use_augmentation:
            x = np.concatenate((x, augmented["train"]["x"]))
            y = np.concatenate((y, augmented["train"]["y"]))
            conditions = np.concatenate((conditions, augmented["train"]["conditions"]))
        estimator = HistGradientBoostingClassifier(max_iter=200, max_leaf_nodes=leaves, learning_rate=0.06,
                                                   l2_regularization=3.0, early_stopping=False, random_state=SEED)
        print(f"Fitting {name}: {len(y)} feature rows", flush=True)
        with threadpool_limits(limits=threads):
            estimator.fit(x, y, sample_weight=condition_weights(y, conditions))
        compare(name, estimator)
        if constrained:
            from .ensemble import AudioBlend
            for weight in plan["blend_candidate_weights"]:
                compare(f"blend_aug31_{weight}", AudioBlend(reference["estimator"], estimator, weight))
    eligible = [row for row in comparisons if row["passes_clean_guard"]]
    selected = min(eligible, key=lambda row: (row["worst_class_error"],
                   -np.mean([item["balanced_accuracy"] for item in row["selection_metrics"].values()]),
                   row["candidate"] != "reference_fixed"))
    selected_name, estimator = selected["candidate"], models[selected["candidate"]]
    model_path = output / "model.joblib"
    joblib.dump({"format_version": 1, "feature_version": FEATURE_VERSION, "estimator": estimator,
                 "threshold": selected["threshold"]}, model_path)
    checksum = sha256_file(model_path)
    intervals = {condition: speaker_bootstrap_comparison(values["y"], predictions["reference_fixed"][condition],
                 predictions[selected_name][condition], values["speakers"], reference["threshold"], selected["threshold"])
                 for condition, values in selection_data.items()}
    with threadpool_limits(limits=threads):
        full_clean = audio_metrics(clean["validation"]["y"], estimator.predict_proba(clean["validation"]["x"])[:, 1], selected["threshold"])
    for name, condition_scores in predictions.items():
        for condition, scores in condition_scores.items():
            values = selection_data[condition]
            np.savez_compressed(output / f"scores-{name}-{condition}.npz", scores=scores, y=values["y"],
                                ids=values["ids"], speakers=values["speakers"], systems=values["systems"])
    import sklearn
    summary = {"status": "trained", "model_version": reference_summary["model_version"] if checksum == reference_summary["checkpoint_sha256"] else f"audio-robust-{checksum[:12]}",
               "feature_version": FEATURE_VERSION, "checkpoint_sha256": checksum,
               "checkpoint_bytes": model_path.stat().st_size, "threshold": selected["threshold"],
               "selected_candidate": selected_name, "reference_model_version": reference_summary["model_version"],
               "reference_checkpoint_sha256": reference_summary["checkpoint_sha256"], "experiment_plan_sha256": identity,
               "training_type": "CPU log-mel summary classifier; controlled AAC/gain/noise comparison",
               "validation_metrics": full_clean, "selection_metrics": selected["selection_metrics"],
               "candidate_comparison": comparisons, "paired_speaker_bootstrap": intervals,
               "improves_declared_development_objective": selected["worst_class_error"] < comparisons[0]["worst_class_error"],
               "evaluation_note": "Development-only selection; all dev speakers were used in the historical reference experiment. No independent test result or real-world accuracy claim.",
               "runtime_versions": {"numpy": np.__version__, "scikit_learn": sklearn.__version__},
               "selection_speakers": selection, "calibration_speakers": calibration,
               "source_provenance_limit": audit["provenance_limit"]}
    write_json(output / "training_summary.json", summary)
    return summary
