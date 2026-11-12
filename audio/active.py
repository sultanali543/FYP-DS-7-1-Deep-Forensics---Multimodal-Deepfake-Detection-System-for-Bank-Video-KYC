"""Choose a verified local audio run without replacing the original checkpoint."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _check_release(run, summary):
    """Keep unevaluated or rejected alternative weights out of the live app."""
    if run.name == "audio_baseline":
        return
    try:
        decision = json.loads((run / "release_decision.json").read_text(encoding="utf-8"))
        candidate = decision["candidate_test"]
        if (decision["release_approved"] is not True
                or decision["no_test_retuning"] is not True
                or decision["candidate_model"] != summary["model_version"]
                or candidate["model_version"] != summary["model_version"]
                or candidate["checkpoint_sha256"] != summary["checkpoint_sha256"]):
            raise ValueError("The candidate did not pass its recorded release decision.")
    except (OSError, KeyError, TypeError) as error:
        raise ValueError("An alternative audio run needs a matching approved release decision.") from error


def selected_audio_run(root):
    root = Path(root).resolve()
    runs = root / "data/runs"
    pointer = runs / "audio_active.json"
    if not pointer.exists():
        return runs / "audio_baseline"
    try:
        metadata = json.loads(pointer.read_text(encoding="utf-8"))
        relative = Path(metadata["run"])
        run = (runs / relative).resolve()
        if metadata.get("format_version") != 1 or relative.is_absolute() or not run.is_relative_to(runs.resolve()) or run == runs.resolve():
            raise ValueError("Invalid audio run path.")
        summary = json.loads((run / "training_summary.json").read_text(encoding="utf-8"))
        digest = hashlib.sha256()
        with (run / "model.joblib").open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        checksum = digest.hexdigest()
        if (checksum != metadata["checkpoint_sha256"] or checksum != summary["checkpoint_sha256"]
                or metadata["model_version"] != summary["model_version"] or summary["status"] != "trained"):
            raise ValueError("Active audio checkpoint metadata differs.")
        _check_release(run, summary)
        return run
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise ValueError("The active audio model pointer is invalid. Use 'python -m audio activate --run data/runs/audio_baseline' to restore the verified reference.") from error


def activate_run(run, root):
    from .predict import load_model

    root, run = Path(root).resolve(), Path(run).resolve()
    runs = (root / "data/runs").resolve()
    if not run.is_relative_to(runs) or run == runs:
        raise ValueError("Active audio runs must be inside this project's data/runs directory.")
    summary, _ = load_model(run)
    if summary.get("status") != "trained":
        raise ValueError("Only a verified trained run can be activated.")
    _check_release(run, summary)
    pointer = runs / "audio_active.json"
    value = {"format_version": 1, "run": run.relative_to(runs).as_posix(),
             "checkpoint_sha256": summary["checkpoint_sha256"], "model_version": summary["model_version"]}
    temporary = pointer.with_suffix(".tmp.json")
    temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    temporary.replace(pointer)
    return {"active_run": str(selected_audio_run(root)), "model_version": summary["model_version"],
            "message": "Restart START_APP.cmd to load this model. The reference checkpoint remains available."}
