# Deep Forensics solo four day build plan

## Target and working assumptions

The supervisor requires the frontend. The personal target is a trained visual baseline, a working local prototype, and a polished frontend within four days. Google Colab GPU access is available. The dataset and notebook need to be obtained or recreated. Budget approximately 6 to 8 focused hours per day; download times and model quality remain uncertain.

The sprint delivers a visual deepfake screening prototype. The interface should preserve a place for audio, clearly marked as not implemented. Adding an audio detector is a later milestone. A visual result must never appear as a completed audio-video verification result.

Build a simple frontend on Day 1 to protect the required deliverable. Finish the baseline next, connect actual inference, and polish the interface after the complete flow works.

## The dataset to obtain first

Use **FaceForensics++**, with these exact selections:

| Selection | Value |
| --- | --- |
| Authentic subset | original_sequences/youtube |
| Manipulated subset | manipulated_sequences/Deepfakes |
| Compression | c23 for both classes |
| File type | videos |
| Initial smoke check | 20 original and 20 manipulated videos |
| Working target | About 200 original and 200 manipulated videos |
| Face samples | Up to 20 frames spread uniformly across each video |
| Labels | real = 0; fake = 1 |

These are sprint sample sizes, not a claim that the data establishes general deepfake detection performance. One manipulation method gives a deliberately narrow first baseline. Expand manipulation diversity after the working prototype.

The [official FaceForensics repository](https://github.com/ondyari/FaceForensics#access) requires a request form and acceptance before supplying its downloader. Check access in the first hour. An existing authorized downloader can be reused. The [dataset documentation](https://github.com/ondyari/FaceForensics/blob/master/dataset/README.md) explains compression and subset options.

Once you have the official script, upload it into Colab and check its help. These commands assume its filename is `download-FaceForensics.py`:

```python
!python download-FaceForensics.py -h
!python download-FaceForensics.py /content/data/ffpp -d original -c c23 -t videos --num_videos 20
!python download-FaceForensics.py /content/data/ffpp -d Deepfakes -c c23 -t videos --num_videos 20
```

Inspect both classes, then repeat the final two commands with `--num_videos 200`. Verify that the script skips existing files before restarting. Follow the current script's help if its options differ. Dataset terms must be accepted through the official process.

If access is pending, request it immediately and check the [official DFDC labeled training sample](https://www.kaggle.com/competitions/deepfake-detection-challenge/data) as an alternative. Its `train_sample_videos` and `metadata.json` provide a small starting set after the account/rules access steps. Use metadata labels and the `original` field for grouping. Its clip-level labels can describe face or voice manipulation, so a visual-only experiment may have modality label noise. Record that limitation.

Set a two-hour access checkpoint. If neither source can be downloaded, continue the required frontend using explicitly marked example results while resolving access. Do not count that as a trained baseline.

| Other proposed dataset | When to use it |
| --- | --- |
| ASVspoof 2019 Logical Access | When starting a separate audio baseline |
| FakeAVCeleb | When evaluating paired visual/audio decisions |
| Full DFDC collection | Later robustness experiments when resources allow |

## Fixed choices for this sprint

| Component | Choice |
| --- | --- |
| Training | Google Colab GPU; persistent backups in Drive |
| Face detector | MTCNN, with fixed face margins and a consistent single-face policy |
| Classifier | ImageNet-pretrained ResNet18 with a trained two-class head |
| Video score | Mean fake score over usable sampled face frames |
| API | FastAPI, local development, one inference worker |
| Frontend | React with Vite, plain CSS, three main screens |
| Storage | Local files for media and SQLite for job metadata/results |
| Explainability | Grad-CAM if integration time permits |
| Report | JSON results first; simple PDF after inference works |

These baseline choices differ from the final models discussed in the proposal. Record them as experimental choices. The [PyTorch transfer learning tutorial](https://docs.pytorch.org/tutorials/beginner/transfer_learning_tutorial.html) demonstrates using a pretrained ResNet18 and training a replacement classifier.

## Day 1 access data and build the frontend shell

### Step 1 first hour

- Create a Drive folder called `DeepForensics`. Keep raw data, manifests, notebooks, checkpoints, and results in separate subfolders.
- Create a clean Colab notebook named `01_visual_baseline.ipynb`.
- Select a GPU runtime and verify that PyTorch sees it:

```python
import torch
print('PyTorch:', torch.__version__)
print('CUDA available:', torch.cuda.is_available())
if torch.cuda.is_available():
    print('GPU:', torch.cuda.get_device_name(0))
```

- Check FF++ access and begin the small download. Save a copy of the notebook to Drive.
- Check the local frontend environment with `node --version` and `npm --version`. Use a supported Node LTS version meeting the current [Vite requirements](https://vite.dev/guide/).

Colab resources are variable. Save important outputs regularly; the [Colab FAQ](https://research.google.com/colaboratory/faq.html) states that GPU availability and runtime limits are not guaranteed.

### Step 2 hours 1 to 3 frontend shell

Scaffold the frontend inside the project folder using:

```powershell
npm create vite@latest frontend -- --template react
cd frontend
npm install
npm run dev
```

Create three views within one application:

1. Upload: project name, purpose, file picker, video preview, supported input limits, Analyze button.
2. Processing: queued/running state, current processing stage, and failure message when relevant.
3. Results: visual verdict, visual model score, sampled frames, audio availability, report download area.

Use a clearly labeled development fixture while inference is being built. Keep the audio module labeled `Not implemented`. Avoid fake progress percentages; show processing stages instead.

### Step 3 hours 3 to 6 prepare the dataset

Create a video manifest before extracting images. Suggested fields:

```text
video_id,path,label,source_ids,split,dataset,compression
```

- Read labels from the known dataset subset or metadata, not filename punctuation alone.
- For FF++, use the official [train](https://github.com/ondyari/FaceForensics/blob/master/dataset/splits/train.json), [validation](https://github.com/ondyari/FaceForensics/blob/master/dataset/splits/val.json), and [test](https://github.com/ondyari/FaceForensics/blob/master/dataset/splits/test.json) pair assignments. Keep subset videos in their original assignments.
- Associate each manipulated video with both participating source IDs. Verify that source IDs are disjoint across splits.
- Count real and fake videos in every split. A small downloader subset may not give ideal counts, so inspect the actual distribution.
- Sample up to 20 timestamps uniformly through each clip. Save the timestamp and video ID for every crop.
- Use one consistently tracked face. Flag no face or ambiguous multiple faces as unusable for this first prototype.
- Detect, crop with a fixed margin, and cache the face images. Resize/crop to the model input and use the selected weight normalization convention consistently.
- Manually inspect at least 10 real and 10 fake crops.

All crops from a video must remain in that video's split. Keep related original/manipulated videos together. Randomly splitting the combined crop folder would allow information leakage.

### Step 4 hours 6 to 8 start training

- Check one batch, labels, image shapes, and class counts.
- Initialize the ResNet18 replacement classifier.
- Train its head for an initial three epochs. Save the first checkpoint and history to Drive.
- If training continues unattended in an active session, use that time for frontend styling or documentation; save model outputs frequently.

**End of Day 1:** frontend screens run locally; both video classes are accessible; manifest and cached crops exist; a training run has started. If data access is still blocked, finish the frontend shell and record the blocker explicitly.

## Day 2 finish the visual baseline and build inference

### Step 5 training recipe

Use these as initial experiment settings, then inspect validation results:

| Setting | Initial value |
| --- | --- |
| Model | ResNet18 with ImageNet weights and two output classes |
| Input | 224 by 224 RGB face crop |
| Batch size | 16 or 32, according to available memory |
| Loss | CrossEntropyLoss; use training-class weights if needed |
| Optimizer | Adam |
| Head training | 3 epochs at learning rate 0.001 |
| Partial fine tuning | Up to 5 epochs for the last residual block and head at 0.0001 |
| Checkpoint selection | Lowest validation loss; preserve the best checkpoint |

During head-only training, freeze the backbone parameters and its batch-normalization statistics. Apply mild augmentation only to training samples. Keep validation/test preprocessing deterministic. Stop or reduce training if validation loss worsens while training loss improves.

Save these together:

```text
visual_resnet18.pt
model_config.json
video_manifest.csv
training_history.csv
validation_metrics.json
```

The configuration should record preprocessing, class mapping, face sampling, seed, model version, and video aggregation. A checkpoint alone is insufficient for reliable reproduction.

### Step 6 evaluate on validation videos

- Calculate each frame's fake score using the trained classifier.
- Average usable frame scores to obtain each video's score.
- Report video-level accuracy, fake precision/recall/F1, confusion matrix, and ROC-AUC when both labels exist.
- Compare with a majority-class predictor. Report the number of videos and class distribution.
- Use validation data for threshold choices. Keep test data untouched until Day 4.
- Inspect false positives and false negatives. Check crops, labels, class imbalance, and source overlap before making architecture changes.

The output is a model score, not an established probability of fraud. A successful training run does not guarantee useful generalization.

### Step 7 standalone inference

Build a function with this interface:

```text
analyze_video(video_path) -> visual score, visual verdict,
                            usable-frame count, timestamps,
                            evidence images, model version
```

Run the same preprocessing and score aggregation as validation. Return an insufficient-evidence status for no usable face, unreadable input, or ambiguous face selection. Measure latency on the local laptop after downloading the checkpoint from Colab. Confirm that the checkpoint loads with CPU inference.

### Step 8 API

Create the following endpoints:

| Endpoint | Purpose |
| --- | --- |
| POST /api/analyses | Validate an upload, create a job, return its ID |
| GET /api/analyses/{id} | Return job state, stage, and available results |
| GET /api/analyses/{id}/report | Download an available report |

Start with short MP4 clips, for example 5 to 30 seconds and a 50 MB upload limit. These are chosen prototype limits. Use unique job folders and persist metadata/results. Run one bounded inference worker outside the request handler. The [FastAPI upload documentation](https://fastapi.tiangolo.com/tutorial/request-files/) explains file handling; its [background task guidance](https://fastapi.tiangolo.com/tutorial/background-tasks/) notes the tradeoffs of heavier computation.

**End of Day 2:** a saved trained model produces a real video-level result through standalone inference and the API.

## Day 3 connect the frontend and add evidence

### Step 9 connect the actual user flow

- Send the uploaded file using multipart form data.
- Store the returned analysis ID and poll its status.
- Display the actual stages: queued, validating, extracting faces, running model, preparing results, complete or failed.
- Render the backend's score and verdict. Remove development fixture results from the real analysis path.
- Show `Analysis scope: Visual only` and `Audio analysis: Not implemented`.
- Present errors and insufficient evidence without producing a REAL verdict.
- Save and reopen a completed result through its job ID.

For visual-only mode, use visual thresholds selected on validation data. An example state mapping is low visual risk, suspicious visual result, or high visual risk. Never imply that an unimplemented audio branch passed.

### Step 10 evidence and report

- Show representative analyzed face crops with timestamps.
- Add Grad-CAM overlays for a few selected frames if the inference flow is stable. Label them model attention/attribution; they do not prove exact manipulation boundaries.
- Hash the original upload using SHA-256.
- Produce a simple PDF containing the analysis ID, file information, hash, model version, visual score, verdict, scope, selected frames, and limitations.
- Verify that the report and UI use the same saved results.

A hash is an integrity fingerprint. Digital signing and a protected audit trail are later work. If heatmaps/PDF threaten the frontend deadline, retain real scored frames and a JSON download, then finish the required interface first.

**End of Day 3:** uploading a held-out clip in the browser reaches actual inference and displays saved results. The report is available if implemented. The frontend remains usable when an analysis fails.

## Day 4 test polish and prepare the demonstration

### Step 11 freeze and evaluate

- Freeze model weights, preprocessing, aggregation, and thresholds.
- Run the held-out test set once for the final reported experiment.
- Save video-level metrics, test clip counts, class distribution, and runtime. Keep frame and video metrics distinct.
- Label any later experiment that uses the test results to guide changes as requiring a fresh evaluation set.

### Step 12 frontend checks

Exercise real clips, manipulated clips, no face, multiple faces, corrupt files, unsupported files, oversized uploads, backend failure, and page reload. Check that report links and evidence timestamps work. Verify desktop layout and a narrow browser window. Confirm that no sample score can be mistaken for actual inference.

### Step 13 delivery pack

- README with local setup, start commands, model placement, and demonstration steps.
- Selected checkpoint and its configuration.
- Manifest and measured evaluation results.
- A small set of held-out demonstration clips that you are permitted to use.
- A working frontend production build.
- One successful example report if reporting was completed.
- A short screen recording as a backup.

Rehearse a five-minute demonstration: purpose, upload, processing stages, visual result, evidence, report, and scope. Explain that the four-day version is a visual baseline within the larger multimodal proposal.

**End of Day 4:** the supervisor's frontend deliverable is ready, the baseline has measured results, and the working prototype has clear scope and reproducible instructions.

## Follow-up audio milestone

When the visual demonstration is complete, obtain ASVspoof 2019 Logical Access for audio experiments. A candidate starting point is the official pretrained [AASIST-L implementation](https://github.com/clovaai/aasist). Verify it on known genuine and spoof examples before integrating. It takes waveform input, so using it changes the spectrogram model path described in the proposal. Preserve its expected preprocessing and check the label direction carefully.

Evaluate audio separately, then obtain [FakeAVCeleb](https://github.com/DASH-Lab/FakeAVCeleb) for paired modality evaluation. Define fusion precedence explicitly and distinguish missing audio from an authentic audio result. Independent modality scores do not measure lip synchronization.

## What to do immediately

1. Check FF++ download access and submit the official request if needed.
2. Create the Drive folders and new Colab notebook; verify GPU availability.
3. Download 20 original and 20 Deepfakes videos using c23 for a smoke check.
4. Check both classes play correctly; then expand toward the working target.
5. Create the frontend upload, processing, and result screens.
6. Build and audit the split manifest before extracting face crops.
