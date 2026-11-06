# Deep Forensics four day prototype plan

Build a local demonstration in which a user uploads a short video, receives separate visual and audio model scores, sees a rule-based verdict and representative heatmaps, and downloads a PDF analysis report.

Planning assumptions: Google Colab GPU for training; no datasets currently downloaded; two team members working approximately 6 to 8 focused hours each day. Dataset access and a working audio checkpoint must be checked on Day 1. Completion depends on those checks. The prototype is an experimental media screening system; results do not establish identity or banking suitability.

## Scope and ownership

| Component | First implementation | Suggested owner |
| --- | --- | --- |
| Visual baseline | ImageNet-pretrained ResNet18 fine-tuned for real/fake face crops | Sultan |
| Face extraction | MTCNN with a consistent face margin and 224 by 224 model input | Sultan |
| Audio baseline | Official pretrained AASIST-L checkpoint, using its waveform preprocessing | Sultan |
| API and processing | FastAPI, FFmpeg, one bounded background worker, persistent job records | Ch Mubashir |
| Frontend | React with Vite and a small custom CSS stylesheet | Ch Mubashir |
| Evidence and reporting | Grad-CAM, input SHA-256, PDF report | Both |
| Evaluation and demo | Fixed held-out examples, metrics and failure cases | Both |

These are sprint choices. Record their differences from the proposal, including ResNet18/MTCNN and waveform-based AASIST audio. An EfficientNet comparison can follow the working prototype.

## Day 1 data preparation and first training run

### First two hours

1. In Colab select a GPU runtime and confirm that PyTorch can use CUDA. Save data manifests, checkpoints and logs to Drive; preprocess and train using Colab's local disk. Copy important outputs back to Drive after each stage.
2. Request FaceForensics++ access through the official repository. It requires approval, so the sprint must not depend on receiving an immediate response.
3. Start with the official Kaggle DFDC training sample if accessible after signing in and accepting its rules. Download the labeled training sample and metadata, not the full competition collection. Confirm access and a successful download early.
4. Download the official AASIST-L checkpoint and obtain labeled ASVspoof 2019 LA audio for a smoke test and later development/evaluation subsets. The initial check needs genuine and spoof examples. Verify the checkpoint and expected input format before building its API adapter.
5. Restore the earlier Colab notebook if available. The current local folder contains the three Word documents; the previously reviewed notebook is not present here.

If the video dataset cannot be accessed by the end of this block, continue the interface/API against clearly labeled development fixtures while resolving access. A trained baseline cannot be promised until labeled data is available. Fixture scores must never appear as real model results.

### Prepare a reproducible dataset

1. Build a manifest containing video path, real/fake label, original/source video identifier, dataset name and split. Read DFDC labels from metadata rather than filename punctuation.
2. Group each original video with its manipulated derivatives. Use an approximately 70/15/15 train/validation/test division by source group; keep identities separate when reliable identity metadata exists. Audit that source groups do not overlap. If FF++ becomes the chosen dataset, use its official splits and retain only related clips within their assigned split.
3. Use the available labeled sample, aiming for a few hundred usable clips. Preserve actual class counts and use a weighted training loss when needed. Keep validation and test distributions explicit.
4. Sample 12 frames uniformly over each clip. Detect and crop faces with a consistent margin, save timestamps and failures, and cache the crops so training does not repeat face detection.
5. Resize using the selected ResNet18 weight preprocessing and normalize consistently. Apply mild training-only augmentation; use deterministic validation/test transforms. Manually inspect crops from both classes.

DFDC labels describe the clip as REAL or FAKE and are not guaranteed to identify the manipulated modality. Treat a visual model trained from these labels as exploratory and record possible label noise. Use modality-specific labels for separate audio/visual evaluation when available.

### Start the visual baseline

1. Load pretrained ResNet18, replace its classifier with two outputs, and define labels consistently as real=0 and fake=1.
2. Initially freeze the backbone, including its batch-normalization statistics, and train the new head. Suggested starting configuration: Adam, head learning rate 0.001, batch size 16 or 32, 3 epochs.
3. Fine-tune the last residual block and head for up to 5 more epochs, using a smaller learning rate such as 0.0001. These are initial experiment settings, not a promised optimum. Use validation loss and stop if it ceases to improve.
4. Save the best validation checkpoint, preprocessing settings, label mapping, seed, split manifest and training history. Do not use the test split to choose a checkpoint.

In parallel, build the frontend upload screen, processing screen and results layout using a clearly marked fixture. Agree on the API response fields before integration.

Day 1 completion gate: accessible labeled video data, audited splits, cached crops, a training run started or completed, an audio checkpoint smoke test, and a frontend shell.

## Day 2 finish the baseline and connect real inference

1. Finish and inspect the visual training run. Use mean fake score over valid sampled faces as the initial video aggregation rule; keep the same rule during validation and inference.
2. Check video-level validation results, including class counts, confusion matrix, precision, recall, F1 and ROC-AUC where both classes are present. Compare with a majority-class baseline. Preserve test data for the final evaluation.
3. Implement an inference function that accepts a video path and returns the visual score, frame timestamps, valid-face count and model version. Match training preprocessing exactly.
4. Extract mono 16 kHz audio using FFmpeg. Adapt AASIST-L with its expected waveform length and padding; process longer speech in chunks. Do not substitute a mel-spectrogram input into this waveform model.
5. Check the audio label mapping carefully. The official AASIST code uses a different class convention from the proposed visual model. Expose one consistent spoof-score direction and verify it with known genuine and spoof examples. Treat raw scores as model outputs until calibrated.
6. Use ASVspoof development examples to choose audio thresholds and keep evaluation examples separate. Silence, missing speech and extraction failures should produce an unavailable/insufficient-evidence status.
7. Implement the following API contract and connect the frontend to actual inference.

| Route | Response |
| --- | --- |
| POST /api/analyses | Accept a validated video and return an analysis ID |
| GET /api/analyses/{id} | Return queued, running, completed or failed status and available results |
| GET /api/analyses/{id}/report | Download the completed PDF |

Use one background inference worker for the local demo and persist job metadata/results. Run inference outside the request handler and return real stage updates. Limit the first version to short MP4 clips, for example 5 to 30 seconds, with a defined file-size limit.

Day 2 completion gate: an uploaded clip receives a real visual result through the web application; the audio adapter either works on known examples or has an explicit unavailable state. If audio integration remains blocked, preserve the working visual prototype and show its actual scope.

## Day 3 fusion heatmaps and reports

1. Choose separate low/high thresholds for each modality from development/validation results. Published paper results and proposal thresholds are not measurements of this implementation.
2. Apply decision rules in an explicit order:

```text
if any available, valid modality exceeds its high spoof threshold:
    verdict = FAKE
elif a required modality has insufficient usable evidence:
    status = INCOMPLETE
    verdict = null
elif both valid modality scores are below their respective low thresholds:
    verdict = REAL
else:
    verdict = SUSPICIOUS
```

The two scores need not be comparable or calibrated probabilities. Keep separate thresholds and record their versions. This fusion does not measure lip synchronization.

3. Generate Grad-CAM overlays for a few representative frames with timestamps. They show model attribution, not confirmed manipulation boundaries.
4. Compute SHA-256 on the original uploaded bytes. Include the hash, analysis ID, timestamp, model versions, modality availability, scores, thresholds, verdict, selected frames and heatmaps in the PDF. A hash does not digitally sign the report.
5. Complete frontend behavior: upload validation; actual processing stages; verdict and modality status; input video preview; frame/heatmap viewer; report download; useful error states. Keep labels clear that scores come from an experimental model.

Day 3 completion gate: the complete upload-to-report flow works on held-out examples. Missing evidence and processing failures remain visible throughout the UI and report.

## Day 4 freeze evaluate and rehearse

1. Freeze model checkpoints, preprocessing, aggregation and thresholds before the held-out test run.
2. Report visual video-level test metrics, test clip counts, audio evaluation results and processing latency separately. State the sample size. A small sample cannot establish very low banking false-acceptance rates.
3. Measure combined detection performance only on paired clips with reliable audio and video ground truth. Without that data, report separate detector metrics and functional integration results. Controlled audio substitutions can exercise the pipeline, but must be labeled synthetic integration cases.
4. Exercise genuine clips, visually manipulated clips, audio-spoof clips, both-modality integration cases, no audio, silence, no face, multiple faces, corrupt input and unsupported/oversized uploads. Check report scores and hashes against the API result.
5. Check that a checkpoint saved in Colab loads in the local inference environment. Save environment dependencies after successful installation rather than assuming packages are interchangeable.
6. Prepare a five-minute demonstration: upload, processing, verdict, frame evidence and PDF. Include one failure/insufficient-evidence case and the measured limitations.
7. Save setup instructions, the evaluation table, model files, sample manifests and a screen recording as a backup demonstration.

Day 4 completion gate: a reproducible baseline, working frontend and API, evidence/report output, honest measured results and a rehearsed demo.

## Suggested repository layout

```text
deep-forensics/
  ml/              preprocessing, training, evaluation and inference code
  backend/         API, worker, fusion and report code
  frontend/        React interface
  configs/         preprocessing, labels and threshold settings
  manifests/       video and audio split manifests
  models/          selected visual/audio checkpoint references
  reports/         evaluation tables and example reports
  README.md        local setup and demo steps
```

Keep raw datasets, credentials and large checkpoints out of normal Git commits. Preserve their access instructions, source attribution and version/checksum references.

## First actions

1. Confirm Colab GPU and Drive persistence.
2. Obtain the labeled DFDC sample; request FF++ access in parallel.
3. Build and audit the video manifest before extracting faces.
4. Start audio checkpoint compatibility checks while visual crops are prepared.
5. Have the second team member build the three frontend screens against the agreed API contract immediately.

## Technical references

- [PyTorch transfer learning tutorial](https://docs.pytorch.org/tutorials/beginner/transfer_learning_tutorial.html) demonstrates replacing a ResNet18 classifier, freezing the feature extractor and fine-tuning.
- [Official DFDC sample and metadata](https://www.kaggle.com/competitions/deepfake-detection-challenge/data) describes the labeled training sample, original-video field and account/rules access requirement.
- [Official FaceForensics repository](https://github.com/ondyari/FaceForensics) describes its approval-based dataset access; its [dataset documentation](https://github.com/ondyari/FaceForensics/blob/master/dataset/README.md) provides split and compression details.
- [Official AASIST implementation](https://github.com/clovaai/aasist) provides pretrained AASIST/AASIST-L models and ASVspoof setup. Its [data loader](https://github.com/clovaai/aasist/blob/main/data_utils.py) defines waveform handling and labels.
- [FastAPI file uploads](https://fastapi.tiangolo.com/tutorial/request-files/) documents upload handling; its [background task guidance](https://fastapi.tiangolo.com/tutorial/background-tasks/) distinguishes small in-process tasks from heavier computation.
- [Vite getting started](https://vite.dev/guide/) documents frontend setup and supported templates.
