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
    predict = commands.add_parser("predict", help="Analyze audio in a video")
    predict.add_argument("--run", type=Path, default=Path("data/runs/audio_baseline"))
    predict.add_argument("--video", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "audit":
        result = audit_pair(args.train, args.validation)
    elif args.command == "train":
        result = fit_baseline(args.train, args.validation, args.output, max_groups=args.max_groups)
    else:
        from .predict import predict_video_audio
        result = predict_video_audio(args.run, args.video)
    print(json.dumps(result, indent=2, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
