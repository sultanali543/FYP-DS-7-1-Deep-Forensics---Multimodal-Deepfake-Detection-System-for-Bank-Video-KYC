"""Command-line entry point: python -m ml --help."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import shutil
import sys

from .common import (
    DATA, DEFAULT_ASSETS, DEFAULT_CROPS, DEFAULT_MANIFEST, DEFAULT_RUNS,
    configure_torch, load_settings, read_json, write_json,
)


def parser():
    command = argparse.ArgumentParser(description="Deep Forensics CPU visual baseline")
    subcommands = command.add_subparsers(dest="command", required=True)
    subcommands.add_parser("doctor", help="Show environment and available resources")
    subcommands.add_parser("setup-assets", help="Download verified pretrained assets; this does not train a detector")

    imported = subcommands.add_parser("import-dfdc", help="Read the small labeled training ZIP or folder")
    imported.add_argument("--source", required=True, type=Path)
    imported.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    imported.add_argument("--seed", type=int, default=42)

    prepare = subcommands.add_parser("prepare", help="Sample and cache face crops")
    prepare.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    prepare.add_argument("--crops", type=Path, default=DEFAULT_CROPS)
    prepare.add_argument("--config", type=Path)
    prepare.add_argument("--limit", type=int, help="Preprocessing smoke check only; not a training run")

    review = subcommands.add_parser("review-crops", help="Create a contact sheet of training crops only")
    review.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    review.add_argument("--crops", type=Path, default=DEFAULT_CROPS)
    review.add_argument("--output", type=Path, default=DATA / "review" / "training_crops.jpg")

    benchmark = subcommands.add_parser("benchmark", help="Measure encoder CPU speed, not model accuracy")
    benchmark.add_argument("--output", type=Path, default=DATA / "review" / "cpu_benchmark.json")

    train = subcommands.add_parser("train", help="Select a frozen encoder and classifier using validation only")
    train.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    train.add_argument("--crops", type=Path, default=DEFAULT_CROPS)
    train.add_argument("--features", type=Path, default=DATA / "features" / "dfdc_sample")
    train.add_argument("--output", type=Path, default=DEFAULT_RUNS / "cpu_baseline")
    train.add_argument("--config", type=Path)
    train.add_argument("--backbones", nargs="+", choices=["efficientnet_b0", "resnet18"])

    evaluate = subcommands.add_parser("evaluate", help="Evaluate a frozen selected model")
    evaluate.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    evaluate.add_argument("--run", type=Path, default=DEFAULT_RUNS / "cpu_baseline")
    evaluate.add_argument("--features", type=Path, default=DATA / "features" / "dfdc_sample")
    evaluate.add_argument("--split", choices=["val", "test"], default="val")

    predict = subcommands.add_parser("predict", help="Analyze a new clip with the trained baseline")
    predict.add_argument("--run", type=Path, default=DEFAULT_RUNS / "cpu_baseline")
    predict.add_argument("--video", required=True, type=Path)
    predict.add_argument("--output", type=Path)

    run = subcommands.add_parser("run", help="Import, prepare, train, and evaluate the selected baseline")
    run.add_argument("--source", required=True, type=Path)
    run.add_argument("--config", type=Path)
    run.add_argument("--output", type=Path, default=DEFAULT_RUNS / "cpu_baseline")
    return command


def doctor():
    import cv2
    import numpy
    import psutil
    import sklearn
    import torchvision
    torch = configure_torch()
    disk = shutil.disk_usage(DATA if DATA.exists() else DATA.parent)
    return {
        "python": sys.version.split()[0], "platform": platform.platform(),
        "ram_gb": round(psutil.virtual_memory().total / 1024**3, 2),
        "available_ram_gb": round(psutil.virtual_memory().available / 1024**3, 2),
        "free_disk_gb": round(disk.free / 1024**3, 2), "logical_cpus": psutil.cpu_count(),
        "torch": torch.__version__, "torchvision": torchvision.__version__,
        "opencv": cv2.__version__, "numpy": numpy.__version__, "scikit_learn": sklearn.__version__,
        "cuda_available": torch.cuda.is_available(), "training_device": "cpu",
        "data_directory": str(DATA),
    }


def run_pipeline(source, settings, output):
    from .data import import_dfdc
    from .evaluate import evaluate_baseline
    from .faces import create_crop_review, ensure_detector, prepare_faces
    from .train import train_baseline

    print("1/4 Import labels and create source-group splits", flush=True)
    manifest = import_dfdc(source, DEFAULT_MANIFEST, settings["seed"])
    print(json.dumps(manifest["counts"], indent=2), flush=True)
    print("2/4 Prepare unambiguous face crops", flush=True)
    detector = ensure_detector()
    crop_summary = prepare_faces(manifest, settings, DEFAULT_CROPS, detector)
    print(json.dumps(crop_summary, indent=2), flush=True)
    create_crop_review(manifest, DEFAULT_CROPS, DATA / "review" / "training_crops.jpg")
    print("3/4 Select the baseline using validation videos", flush=True)
    feature_root = DATA / "features" / "dfdc_sample"
    output = Path(output)
    if (output / "model.pt").exists():
        summary = read_json(output / "training_summary.json")
        if summary["manifest_fingerprint"] != manifest["fingerprint"] or summary["settings"] != settings:
            raise ValueError("Existing run settings differ. Choose a new --output directory.")
        print("Reusing this run's existing trained artifact.", flush=True)
    else:
        summary = train_baseline(manifest, settings, DEFAULT_CROPS, feature_root, output)
    print("4/4 Evaluate the frozen selected model on held-out test videos", flush=True)
    if (output / "test_metrics.json").exists():
        report = read_json(output / "test_metrics.json")
        print("Reusing the saved final test report.", flush=True)
    else:
        report = evaluate_baseline(manifest, output, feature_root, "test", settings["bootstrap_repeats"])
    return {"model_version": summary["model_version"], "selected_backbone": summary["selected_backbone"],
            "run_directory": str(output.resolve()), "test": report}


def main(argv=None):
    arguments = parser().parse_args(argv)
    try:
        if arguments.command == "doctor":
            result = doctor()
        elif arguments.command == "setup-assets":
            from .faces import ensure_detector
            from .features import make_encoder
            result = {"face_detector": str(ensure_detector()), "backbones": []}
            for name in ("efficientnet_b0", "resnet18"):
                encoder, _, dimension = make_encoder(name)
                result["backbones"].append({"name": name, "feature_dimension": dimension})
                del encoder
            result["status"] = "Pretrained assets ready; no deepfake classifier has been trained."
        elif arguments.command == "import-dfdc":
            from .data import import_dfdc
            manifest = import_dfdc(arguments.source, arguments.manifest, arguments.seed)
            result = {"manifest": str(arguments.manifest), "counts": manifest["counts"],
                      "fingerprint": manifest["fingerprint"]}
        elif arguments.command == "prepare":
            from .faces import ensure_detector, prepare_faces
            result = prepare_faces(read_json(arguments.manifest), load_settings(arguments.config),
                                   arguments.crops, ensure_detector(), arguments.limit)
        elif arguments.command == "review-crops":
            from .faces import create_crop_review
            result = create_crop_review(read_json(arguments.manifest), arguments.crops, arguments.output)
        elif arguments.command == "benchmark":
            from .benchmark import benchmark_encoders
            result = benchmark_encoders()
            write_json(arguments.output, result)
        elif arguments.command == "train":
            from .train import train_baseline
            result = train_baseline(read_json(arguments.manifest), load_settings(arguments.config),
                                    arguments.crops, arguments.features, arguments.output, arguments.backbones)
        elif arguments.command == "evaluate":
            from .evaluate import evaluate_baseline
            result = evaluate_baseline(read_json(arguments.manifest), arguments.run, arguments.features, arguments.split)
        elif arguments.command == "predict":
            from .predict import predict_video
            result = predict_video(arguments.run, arguments.video)
            if arguments.output:
                write_json(arguments.output, result)
        else:
            result = run_pipeline(arguments.source, load_settings(arguments.config), arguments.output)
        print(json.dumps(result, indent=2, allow_nan=False), flush=True)
        return 0
    except (ValueError, FileNotFoundError, FileExistsError, OSError) as error:
        print(f"Baseline stopped: {error}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
