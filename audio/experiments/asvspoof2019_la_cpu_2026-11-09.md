# ASVspoof 2019 LA CPU audio baseline — 2026-11-09

## Data and provenance

The source was the [Bisher community Parquet reupload](https://huggingface.co/datasets/Bisher/ASVspoof_2019_LA/tree/main/data), not the official Edinburgh archive. The train file was 1,586,086,073 bytes, SHA-256 `b4eea1063bbcfa0c1cef1b69a96ad8b787c32f662005562b899cd4b461739619`. The validation file was 1,575,535,827 bytes, SHA-256 `9d2c340bb7f04c2d63ac018b224ecdb8c1855c789247232608b650f86c189b16`. Neither dataset file is committed.

The files contain 25,380 training utterances (2,580 bona fide; 22,800 spoof) and 24,844 development utterances (2,548 bona fide; 22,296 spoof), matching the [official 2019 evaluation plan](https://www.asvspoof.org/asvspoof2019/asvspoof2019_evaluation_plan.pdf). Training and development speakers and audio IDs are disjoint. The six spoof system IDs each contain 3,800 training and 3,716 development utterances. The embedded audio is readable 16 kHz mono FLAC. These checks support the reupload's structure but do not verify byte-for-byte equivalence to the official audio. [ASVspoof 2021](https://www.asvspoof.org/index2021.html) supplied evaluation data, not new train/dev partitions.

## Method

Every utterance was decoded directly from Parquet. A 25 ms window and 10 ms hop produced 128-band log-mel spectra. The first 40 cepstral coefficients, their differences, and utterance-level distribution statistics formed a 241-element vector. The full 2019 LA training partition fitted three CPU candidates with inverse-frequency class weights: logistic regression at C=0.1 and C=1, and histogram gradient boosting with 100 iterations. The validation partition selected the candidate and FAKE threshold by balanced accuracy, then ROC AUC. No validation samples fitted the feature scaler or classifier. The 2019 evaluation and 2021 partitions were not downloaded or inspected.

The selected model is **histogram gradient boosting** (`audio-asv19la-095854128b36`), with a **0.762300** FAKE threshold and SHA-256 `095854128b36c6d7eec03f8fc853e698df974caaf2297493659c389bba5189eb`. Its local checkpoint is 688,214 bytes and is excluded from Git.

## Validation results

| Model | Balanced accuracy | ROC AUC |
| --- | ---: | ---: |
| Logistic regression, C=0.1 | 96.86% | 0.9955 |
| Logistic regression, C=1 | 96.66% | 0.9950 |
| Histogram gradient boosting, 100 iterations | **97.31%** | 0.9948 |

For the selected model, validation accuracy was **98.38%**, fake recall **98.65%**, and real false-alarm rate **4.04%**. The confusion matrix was `[[2445 real accepted, 103 real flagged], [300 fakes missed, 21996 fakes flagged]]`. The majority-class accuracy was 89.74% and balanced accuracy 50%. Spoof recall by system was A01 99.97%, A02 99.97%, A03 99.57%, A04 95.08%, A05 98.84%, A06 98.49%. These subgroup figures were inspected after model selection and were not used to retune it. The accompanying [JSON summary](asvspoof2019_la_cpu_2026-11-09.json) contains all candidate metrics.

**These are development-set model-selection numbers, not an independent test result.** The threshold and model were chosen on this same split. The next evaluation needs the separate official 2019 LA evaluation partition or an ASVspoof 2021 evaluation partition, with the checkpoint frozen beforehand. More importantly, ASVspoof LA audio differs from compressed bank video KYC audio; the measured development score does not establish real-world performance. The frontend displays visual and audio scores separately without claiming a validated fused decision.

Environment: Windows, Python 3.13.3, NumPy 2.5.4, SciPy 1.18.1, scikit-learn 1.9.1, PyArrow 23.0.1, SoundFile 0.14.0, imageio-ffmpeg 0.8.1. The training command and inference instructions are in [audio/README.md](../README.md).
