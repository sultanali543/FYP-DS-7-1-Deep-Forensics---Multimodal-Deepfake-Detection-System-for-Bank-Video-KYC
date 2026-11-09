# ASVspoof 2019 LA CPU audio baseline

This stage trains a separate spoofed-speech detector from the **ASVspoof 2019 Logical Access** training split. The 2021 challenge released new evaluation sets but no new training or development set, so 2019 LA is the correct training source. The downloaded Hugging Face Parquet files are a **community reupload**, not an official archive. The importer verifies their official split totals, label distribution, attack IDs, disjoint speakers, embedded FLAC format, and SHA-256 hashes. That does not prove byte-for-byte equivalence with the Edinburgh original.

The feature extractor streams each Parquet row group directly. It decodes 16 kHz mono FLAC, creates 128-band log-mel frames, takes 40 cepstral coefficients, and summarizes their distribution and change over time. This gives 241 features per utterance. Two scaled logistic models and one histogram gradient boosting model are compared on the validation split. Class weights offset the roughly 9:1 spoof-to-genuine imbalance. Validation balanced accuracy, ROC AUC, and a validation-selected threshold select the artifact. **Validation scores are not held-out test results.** A separate 2019 evaluation or 2021 evaluation set is still needed before making a final benchmark claim.

This compact classifier is intended for an 8 GB CPU laptop. It is not the proposal's eventual pretrained speech backbone or an official LFCC-LCNN reproduction. It gives a measured audio baseline and a working pipeline to improve on with university GPU access.

## Run on this laptop

From the project root, with the existing `.venv`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r audio\requirements.txt
.\.venv\Scripts\python.exe -m audio audit --train "C:\Users\hp\Downloads\train-00000-of-00001.parquet" --validation "C:\Users\hp\Downloads\validation-00000-of-00001.parquet"
.\.venv\Scripts\python.exe -m audio train --train "C:\Users\hp\Downloads\train-00000-of-00001.parquet" --validation "C:\Users\hp\Downloads\validation-00000-of-00001.parquet"
```

`data/runs/audio_baseline/` contains the ignored feature cache, audit, checkpoint, and training summary. The command resumes feature extraction after interruption. It refuses to overwrite a finished model; choose a new `--output` directory for a different experiment. For a short pipeline check, add `--max-groups 1`; this extracts only one row group per split and does **not** train a model.

After training, `START_APP.cmd` uses the checkpoint automatically. An MP4 with a usable audio track shows separate visual and audio scores. There is no unvalidated fused fraud score. If speech is missing or too quiet, the audio field reports insufficient evidence without inventing a score. The uploaded backend copy is still deleted after analysis. The original video and Parquet downloads stay untouched.

To inspect the audio score alone:

```powershell
.\.venv\Scripts\python.exe -m audio predict --video "C:\path\to\clip.mp4"
```

Dataset/source references: [official 2019 evaluation plan](https://www.asvspoof.org/asvspoof2019/asvspoof2019_evaluation_plan.pdf), [2021 challenge data policy](https://www.asvspoof.org/index2021.html), [community Parquet reupload](https://huggingface.co/datasets/Bisher/ASVspoof_2019_LA/tree/main/data).
