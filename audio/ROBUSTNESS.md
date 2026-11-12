# Audio robustness and independent evaluation

This CPU experiment retains the original checkpoint and compares five declared candidates: the frozen reference, a development-calibrated reference threshold, a longer clean-data histogram boosting model, and two channel-augmented boosting models. It does not implement the proposal's eventual pretrained neural speech model.

## Reproduce training

The default run uses all 25,380 clean training features and two augmented views of 1,000 genuine and 1,000 spoof training utterances. The channel conditions are AAC-LC 32 kb/s plus random gain, and AAC-LC 64 kb/s plus gain and 20–30 dB synthetic noise. These simulate selected conditions, not all WhatsApp/HE-AACv2 or real-world noise. Both labels receive the same transformations, with equal total training weight per class and condition. Personal diagnostic videos never fit/select candidates.

Development includes all clean utterances and two views of 800 genuine and 800 spoof utterances. Ten development speakers calibrate thresholds; ten other speakers compare candidates. All views stay with their source. Thresholds minimize the largest class error across conditions. Selection also requires each clean-data class error to stay within one percentage point of the reference. **These are development results:** the historical baseline already used the full development split.

```powershell
.\.venv\Scripts\python.exe -m audio train-robust --train "C:\Users\hp\Downloads\train-00000-of-00001.parquet" --validation "C:\Users\hp\Downloads\validation-00000-of-00001.parquet" --output data/runs/audio_robustness_2026-11-11_batch
```

Add `--max-groups 2` for an extraction check without training; remove it to resume. Atomic feature caches reject incompatible sources/configuration. Temporary codec files are removed. FFmpeg has a bounded timeout and one retry. A finished run cannot be overwritten. Keep the laptop awake during training.

Outputs include the declared experiment plan, dataset audit, candidate comparisons, saved development scores, paired speaker bootstrap intervals, selected weights, and checksum. Source Parquet files remain a community reupload with official-byte equivalence unverified.

The first experiment rejected its augmented candidates because their unconstrained thresholds raised clean genuine false alarms. The follow-up constrains calibration FPR and FNR to the reference's calibration values plus one percentage point. It compares one augmented 31-leaf classifier and fixed 25%/50% blends with the reference. Candidate comparison still uses the other development speakers. These follow-up choices were made before any independent test predictions.

```powershell
.\.venv\Scripts\python.exe -m audio train-robust --train "C:\Users\hp\Downloads\train-00000-of-00001.parquet" --validation "C:\Users\hp\Downloads\validation-00000-of-00001.parquet" --output data/runs/audio_robustness_2026-11-12_constrained --constrained --reuse-channels data/runs/audio_robustness_2026-11-11_batch
```

Reusing channel features requires matching source hashes, selected IDs, extractor/augmentation versions, FFmpeg checksum, and cache identity. It reuses input features, not prior test scores. The selected candidate and its threshold must be frozen before external evaluation. A release check may reject that candidate; it must not retune it against the test result.

## Independent evaluation

The evaluator uses the app's shared inference function and saved threshold; it never fits or selects a model. It reports class errors, AUC, EER, confusion matrix, per-attack missed spoofs, time, and coverage. Unreadable/quiet audio is unscored, never REAL. Metrics are conditional on scored clips, so inspect class coverage too.

EER uses local linear interpolation of a tie-aware ROC curve, explicitly different from the official nearest-discrete-DET convention. No min t-DCF is claimed without the corresponding ASV system scores/costs.

CSV manifests require `audio_id,path,label,speaker_id,system_id,split,source`. Paths can be absolute or relative to the manifest. Labels accept REAL/FAKE or bonafide/spoof. Test mode rejects train/dev IDs, non-test splits, duplicate files, and speakers present in the model's training/development audit. Use `--purpose development` only for a development manifest. Renaming validation files does not create a test set.

Import an existing official 2019 LA evaluation folder:

```powershell
.\.venv\Scripts\python.exe -m audio eval-manifest --protocol "C:\path\ASVspoof2019.LA.cm.eval.trl.txt" --audio-dir "C:\path\ASVspoof2019_LA_eval\flac" --output data/evaluation/manifest.csv
.\.venv\Scripts\python.exe -m audio evaluate --manifest data/evaluation/manifest.csv --run data/runs/audio_baseline --output data/evaluation/reference
```

For limited storage, the selective downloader uses the official Edinburgh archive. It chooses 500 genuine and 500 spoof clips by speaker/attack strata with seed 20261112 before scoring. It validates HTTP ranges, ZIP CRC per member, and local SHA-256. It refuses full-file responses or more than 700 MiB of archive transfer per invocation; the full archive checksum is not computed.

```powershell
.\.venv\Scripts\python.exe -m audio.official_eval --output data/audio_official_eval_2019_1000
.\.venv\Scripts\python.exe -m audio evaluate --manifest data/audio_official_eval_2019_1000/manifest.csv --run data/runs/audio_baseline --output data/evaluation/reference_1000
.\.venv\Scripts\python.exe -m audio evaluate --manifest data/audio_official_eval_2019_1000/manifest.csv --run data/runs/audio_robustness_2026-11-12_constrained --output data/evaluation/candidate_1000
```

This is a balanced research subset, not the full challenge benchmark or its natural class prevalence. The run shown above is the frozen candidate from the constrained follow-up; the first run selected the original reference. Never tune model/threshold choices against these results. Record failures honestly; further development needs a fresh independent assessment.

Contains information from [ASVspoof 2019, University of Edinburgh/CSTR](https://doi.org/10.7488/ds/2555), made available under the [Open Data Commons Attribution License](https://opendatacommons.org/licenses/by/1-0/). The downloader stores the publisher's license locally. Data and per-clip outputs stay out of Git.

## Select or restore the app's audio model

The candidate in this report failed its release check, so it cannot be activated in the connected app. After a future candidate passes an independently recorded release decision, select that verified local run and restart `START_APP.cmd`:

```powershell
.\.venv\Scripts\python.exe -m audio activate --run data/runs/audio_approved_candidate
```

The backend checks `data/runs/audio_active.json` against checkpoint/version hashes and the approved release decision for an alternative run. Without a pointer it uses the original baseline. An invalid or rejected pointer fails explicitly. Activation does not retrain or overwrite weights.

Restore the reference with:

```powershell
.\.venv\Scripts\python.exe -m audio activate --run data/runs/audio_baseline
```

For another laptop, transfer the chosen run's `model.joblib`, `training_summary.json`, `dataset_audit.json`, and `release_decision.json` for an approved alternative, together with matching code/dependencies. Activate the run there. Keep weights, datasets, and the local pointer out of Git.
