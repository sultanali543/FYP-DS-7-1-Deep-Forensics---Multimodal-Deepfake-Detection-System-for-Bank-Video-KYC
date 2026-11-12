# Audio robustness experiment — 12 November 2026

**A CPU candidate improved balanced accuracy from 84.0% to 86.0% on a preselected official 1,000-clip evaluation subset, but increased genuine false alarms from 8 to 12 out of 500. It failed the declared release check and was not activated.** The connected app retains the original audio baseline. The training, evaluation, and verified model-selection workflows are implemented and tested.

## Independent result

Both checkpoints and thresholds were frozen before this evaluation. No test score was used to tune them or select another candidate afterward.

| Measure | Reference | Frozen candidate |
| --- | ---: | ---: |
| Accuracy / balanced accuracy | 84.00% | 86.00% |
| Genuine false alarms | 8 / 500 (1.60%) | 12 / 500 (2.40%) |
| Spoofs accepted as REAL | 152 / 500 (30.40%) | 128 / 500 (25.60%) |
| ROC AUC | 0.94756 | 0.954744 |
| EER, local ROC interpolation | 11.80% | 9.60% |
| Analysis coverage | 1,000 / 1,000 | 1,000 / 1,000 |
| Saved decision threshold | 0.762300 | 0.731675 |

With rows representing true REAL/FAKE and columns predicted REAL/FAKE, confusion matrices are `[[492, 8], [152, 348]]` and `[[488, 12], [128, 372]]`. The candidate correctly detected 24 additional spoofs while falsely flagging four additional genuine utterances. This is a measured tradeoff, not an unqualified accuracy improvement.

Paired bootstrap resampling of 67 protocol speaker IDs, with 500 valid resamples, gave candidate-minus-reference 95% intervals of **0.0 to +1.80 percentage points** for genuine false alarms and **−6.48 to −3.04 points** for missed spoofs. These intervals describe this selected subset, not population guarantees.

Attack A17 remains especially weak: both models missed **37 of 38** sampled spoofs. For A18, missed spoofs changed from **34/38 to 30/38**. These post-evaluation findings were not used to retrain or retune either model.

## Official evaluation provenance

The subset comes directly from the [University of Edinburgh/CSTR ASVspoof 2019 release](https://doi.org/10.7488/ds/2555). The downloader reads the official LA ZIP central directory and evaluation protocol with validated HTTP ranges, selects 500 genuine and 500 spoof IDs by speaker/attack strata using seed **20261112**, and verifies each downloaded member's CRC and local SHA-256. Selection was recorded before model scoring. Train/development speaker overlap checks passed. Attack IDs A07–A19 are represented.

The complete archive is 7,640,952,520 bytes; the selected FLAC audio is approximately 59.9 MB. Archive transfer for this run was **73,862,702 bytes**, including metadata and headers fetched with ranges. The entire archive checksum was not computed. Manifest SHA-256: `9b543e90585ec27664c0b514ca148468b27969e92c53bc56f503623c6a31f71f`.

This is a balanced research subset, not the full challenge benchmark or its natural class prevalence. EER uses local tie-aware ROC interpolation rather than the official nearest-discrete-DET convention. No min t-DCF is reported without a corresponding speaker-verification system. Timing was recorded while both evaluation processes ran concurrently and is not a standalone laptop latency benchmark.

Contains information from **ASVspoof 2019, University of Edinburgh/CSTR**, made available under the [Open Data Commons Attribution License](https://opendatacommons.org/licenses/by/1-0/). The publisher's license and per-file integrity records are retained with the local data.

## Training and development

The original community Parquet train/dev sources were re-audited. They contain 25,380 training and 24,844 development utterances, with disjoint source speaker IDs. Their structure and hashes match the baseline audit; byte equivalence to the official training archive remains unverified.

Training reuses all clean features and adds AAC/gain/noise views of 1,000 genuine and 1,000 spoof training utterances. Two channel profiles add 4,000 feature rows. Class and channel weights balance their total contributions. The feature extractor remains the shared 16 kHz, 128-band log-mel / 40-cepstrum summary pipeline. This is not a pretrained neural spoof detector.

Development includes all clean utterances and two channel views of 800 genuine and 800 spoof utterances. Ten speaker IDs calibrate thresholds; ten different IDs compare candidates. The latter group is still development data, not an independent test: the original baseline previously used the entire development split. No personal video entered fitting or candidate selection.

The first experiment compared the frozen reference, a recalibrated reference, a clean 200-iteration model, and augmented 15/31-leaf models. Their unconstrained robust thresholds reduced noisy-spoof misses but increased clean genuine false alarms beyond the one-point limit, so the reference was retained.

Before independent scoring, a follow-up added clean class-error constraints during calibration and compared the augmented 31-leaf classifier with fixed 25%/50% reference blends. It selected the **50% blend** using the declared development criterion. Its selection-speaker results were:

| Development condition | Reference balanced accuracy | Candidate balanced accuracy | Reference genuine false alarms | Candidate genuine false alarms |
| --- | ---: | ---: | ---: | ---: |
| Clean | 95.81% | 95.67% | 7.10% | 8.09% |
| AAC 32 kb/s + gain | 92.34% | 92.88% | 12.50% | 13.00% |
| AAC 64 kb/s + gain + synthetic noise | 68.56% | 71.75% | 8.50% | 10.25% |

The worst class error across these conditions fell from 54.375% to 46.25%. The clean genuine increase remained within the declared one-percentage-point development guard. This did not imply that genuine errors would improve independently.

## Release decision and remaining limitations

The predeclared external release rule required improved development performance, complete test coverage, improved balanced accuracy, and **no observed increase in either test class error**. The final condition failed. No new threshold was chosen from test results. The reference stays active; the candidate remains an experimental artifact.

- Active reference: `audio-asv19la-095854128b36`; checkpoint SHA-256 `095854128b36c6d7eec03f8fc853e698df974caaf2297493659c389bba5189eb`.
- Candidate: `audio-robust-5c5428f0d846`; checkpoint SHA-256 `5c5428f0d8462863257e2820fd55a44b18c7409827ea2144a02fffd9d00a1470`; 1,919,618 bytes.
- Both models still flag the inspected private interview example. The false alarm is unresolved; private scores/media remain outside Git.
- Codec simulation is AAC-LC, not a reproduction of every WhatsApp HE-AACv2 processing chain. Clean benchmark speech does not establish bank Video-KYC performance.
- Speech activity/quality modeling and the proposal's pretrained speech backbone remain future work. Further development needs independent assessment beyond this now-inspected subset.

## Verification and reproduction

**64 Python tests passed** after the model-activation safeguard, covering audio, visual regression, and the backend. **15 frontend tests passed** during the experiment, and the live frontend build succeeded. Dependency checks passed. The Python suite emitted one existing Starlette/httpx deprecation warning.

A real FastAPI upload ran both installed models, returned complete multimodal results, deleted the backend copy, and preserved the source file's hash. The reference audio score exactly matched its earlier recorded value. The active pointer and model checksum checks passed. No visual weights or thresholds were changed.

See [commands and design](../ROBUSTNESS.md) and the [aggregate machine-readable report](asvspoof2019_la_robustness_2026-11-12.json). The completed runs are local under `data/runs/audio_robustness_2026-11-11_batch/` and `data/runs/audio_robustness_2026-11-12_constrained/`; datasets, checkpoints, per-clip predictions, and local activation settings are excluded from Git.
