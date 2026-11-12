"""Run: python -m audio audit|train|predict."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .dataset import audit_pair
from .train import fit_baseline


def main(argv=None):
    parser = argparse.ArgumentParser(description="ASVspoof 2019 LA CPU audio baseline")
    commands = parser.add_subparsers(dest="command", required=True)
    audit = commands.add_parser("audit", help="Check counts, schema, labels and sample audio")
    train = commands.add_parser("train", help="Extract features and train on the full official train split")
    for item in (audit, train):
        item.add_argument("--train", type=Path, required=True)
        item.add_argument("--validation", type=Path, required=True)
    train.add_argument("--output", type=Path, default=Path("data/runs/audio_baseline"))
    train.add_argument("--max-groups", type=int, help="Feature extraction smoke check only; does not train")
    robust = commands.add_parser("train-robust", help="Compare channel-augmented CPU candidates using development data only")
    robust.add_argument("--train", type=Path, required=True)
    robust.add_argument("--validation", type=Path, required=True)
    robust.add_argument("--reference-run", type=Path, default=Path("data/runs/audio_baseline"))
    robust.add_argument("--output", type=Path, required=True)
    robust.add_argument("--train-per-class", type=int, default=1000)
    robust.add_argument("--dev-per-class", type=int, default=800)
    robust.add_argument("--threads", type=int, default=2)
    robust.add_argument("--max-groups", type=int, help="Partial channel extraction only; does not train")
    robust.add_argument("--constrained", action="store_true", help="Follow-up: constrain calibration clean errors; compare augmented model and reference blends")
    robust.add_argument("--reuse-channels", type=Path, help="Reuse a complete run's verified matching channel feature cache")
    evaluate = commands.add_parser("evaluate", help="Score a labeled manifest using the saved threshold; never fit")
    evaluate.add_argument("--manifest", type=Path, required=True)
    evaluate.add_argument("--run", type=Path, default=Path("data/runs/audio_baseline"))
    evaluate.add_argument("--output", type=Path, required=True)
    evaluate.add_argument("--purpose", choices=("development", "test"), default="test")
    evaluate.add_argument("--threads", type=int, default=2)
    protocol = commands.add_parser("eval-manifest", help="Import the official 2019 LA evaluation protocol")
    protocol.add_argument("--protocol", type=Path, required=True)
    protocol.add_argument("--audio-dir", type=Path, required=True)
    protocol.add_argument("--output", type=Path, required=True)
    activate = commands.add_parser("activate", help="Choose a verified local run for the connected app")
    activate.add_argument("--run", type=Path, required=True)
    predict = commands.add_parser("predict", help="Analyze audio in a video")
    predict.add_argument("--run", type=Path, default=Path("data/runs/audio_baseline"))
    predict.add_argument("--video", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "audit":
        result = audit_pair(args.train, args.validation)
    elif args.command == "train":
        result = fit_baseline(args.train, args.validation, args.output, max_groups=args.max_groups)
    elif args.command == "train-robust":
        from .robustness import fit_robustness
        result = fit_robustness(args.train, args.validation, args.reference_run, args.output,
                                train_per_class=args.train_per_class, dev_per_class=args.dev_per_class,
                                threads=args.threads, max_groups=args.max_groups,
                                constrained=args.constrained, reuse_channels=args.reuse_channels)
    elif args.command == "evaluate":
        from .evaluate import evaluate_manifest
        result = evaluate_manifest(args.manifest, args.run, args.output, purpose=args.purpose, threads=args.threads)
    elif args.command == "eval-manifest":
        from .evaluate import manifest_from_2019_protocol
        result = manifest_from_2019_protocol(args.protocol, args.audio_dir, args.output)
    elif args.command == "activate":
        from .active import activate_run
        result = activate_run(args.run, Path(__file__).resolve().parents[1])
    else:
        from .predict import predict_video_audio
        result = predict_video_audio(args.run, args.video)
    print(json.dumps(result, indent=2, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
