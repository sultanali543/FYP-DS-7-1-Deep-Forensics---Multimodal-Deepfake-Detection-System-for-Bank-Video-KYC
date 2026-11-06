# CPU visual baseline

This is the first **visual-only research baseline** for Deep Forensics. Python code handles dataset labels, face extraction, training, evaluation, and prediction. The React frontend remains a separate demonstration until a backend connects it to a trained checkpoint.

## What is trained and why

We compare two ImageNet-pretrained image encoders, **EfficientNet-B0** and **ResNet18**, with a small regularized logistic regression classifier. The encoder stays frozen. Only the classifier learns from DFDC labels. This is transfer learning with cached features, not end-to-end CNN fine-tuning.

EfficientNet-B0 is the initial candidate because its official full classification model is about 5.3 million parameters and 0.39 GFLOPS, compared with ResNet18's 11.7 million and 1.81 GFLOPS. Removing the ImageNet classification layer leaves about 4.0 million and 11.2 million encoder parameters respectively. Parameter counts and ImageNet accuracy do not establish deepfake detection quality. Validation results decide which encoder is saved; there is no model that is best for every dataset.

Frozen features make this experiment practical on an 8 GB laptop without a GPU. Class weighting, source grouping, validation selection, and honest held-out evaluation help measure its quality. They cannot guarantee a target accuracy. If the result is weak, record it and use the university GPU to fine-tune in a separate experiment.

Tools:

| Tool | Purpose |
| --- | --- |
| Python, PyTorch, TorchVision | Pretrained encoders and portable model checkpoint |
| OpenCV YuNet 2023mar | CPU face detection and video decoding |
| NumPy, scikit-learn | Feature cache, scaling, logistic classifier, metrics |
| Matplotlib | ROC curve and confusion matrix |
| pytest | Correctness tests, including split leakage and export parity |

YuNet is used because it is small and runs on CPU. The 2023mar model matches OpenCV 4.x. It is a face detector, not a deepfake detector. Downloads come from the official OpenCV and PyTorch sources. YuNet is verified against its publisher's Git LFS SHA-256; TorchVision checks its published weight hash.

## Dataset: download only the labeled training sample

1. Sign in to the [official DFDC Data page](https://www.kaggle.com/competitions/deepfake-detection-challenge/data).
2. Complete Kaggle phone verification if required and review/accept its competition rules in your account.
3. In Data Explorer, select **train_sample_videos**, then download that folder. It contains 400 MP4 files and `metadata.json`.
4. Keep the ZIP. Do not unpack it: the importer opens one video at a time in a temporary workspace file and removes that temporary file afterward.

Do not select the full 470+ GB dataset or a 10 GB training shard. The unlabeled `test_videos` folder is unnecessary for this experiment. If Kaggle downloads all competition files anyway, the importer still reads only the labeled videos next to `metadata.json`.

Use a ZIP or a folder containing exactly one `metadata.json`, with each labeled video beside it. No credentials are needed by the training scripts. Do not paste passwords, phone verification codes, or Kaggle tokens into chat or Git.

The workflow keeps a single archive, small face images, cached vectors, and a model checkpoint. Exact disk usage depends on Kaggle's archive and how many faces can be extracted. Allow several GB for the archive plus approximately 1-2 GB for the Python environment and working outputs; measure actual free space with `doctor`. No Google Drive or paid cloud service is required for this CPU experiment.

## Run on Windows

Open the project folder. Python 3.13.3 on Windows 11 was used to verify this setup. The pinned CPU PyTorch wheels need a supported 64-bit Python version.

1. Double-click **SETUP_BASELINE.cmd** once. It creates `.venv`, installs the tested packages, and downloads the small pretrained assets. This step does not train a deepfake classifier.
2. Double-click **TRAIN_BASELINE.cmd**. Paste the full path to your DFDC training ZIP when asked, then press Enter.
3. Keep the laptop plugged in. The program prints progress, reuses valid crop/feature caches, compares both encoders on validation videos, saves the selected model, and evaluates the held-out test split.
4. Read the report in `data/runs/cpu_baseline/test_metrics.json` and the matching `test_evaluation.png`. Check balanced accuracy, AUC, fake recall, false alarms on real clips, and how many videos were analyzable.
5. Double-click **PREDICT_VIDEO.cmd** and paste an MP4 path to run the trained visual baseline on another clip.

If interrupted, run the training launcher again with the same archive. Use a new output directory for a changed experiment. Do not tune on final test results or try many random seeds until the test score looks good.

For a more careful first run, use PowerShell from the project root to inspect preprocessing before training:

```powershell
.\.venv\Scripts\python.exe -m ml import-dfdc --source "C:\path\to\training-sample.zip"
.\.venv\Scripts\python.exe -m ml prepare
.\.venv\Scripts\python.exe -m ml review-crops
# Open data/review/training_crops.jpg and confirm crops cover faces.
.\.venv\Scripts\python.exe -m ml train
.\.venv\Scripts\python.exe -m ml evaluate --split test
```

`prepare --limit 4` is a preprocessing smoke check. The training command refuses to use an incomplete crop cache. Run `prepare` without a limit before training. The review sheet uses training videos only; it never displays held-out test crops for manual selection.

Other useful commands:

```powershell
.\.venv\Scripts\python.exe -m ml doctor
.\.venv\Scripts\python.exe -m ml benchmark
.\.venv\Scripts\python.exe -m pytest ml\tests -q
.\.venv\Scripts\python.exe -m ml predict --video "C:\path\to\clip.mp4" --output data\prediction.json
.\.venv\Scripts\python.exe -m ml run --source "C:\path\to\training-sample.zip" --output data\runs\experiment_02
```

The benchmark uses synthetic tensors to check encoder operation and CPU speed. It cannot measure detection accuracy. Its timing excludes video decoding, face detection, and disk access. Close unnecessary applications if `doctor` reports little available RAM; batch size can be reduced in the settings for a new run.

## How the experiment works

1. **Import labels.** REAL maps to 0; FAKE maps to 1. Filenames are not used as labels. The manifest records archive SHA-256, metadata fingerprint, labels, and split memberships.
2. **Group related source clips.** A fake and its referenced original are kept together, including chains and originals absent from the sample. Five stratified source-group folds give approximately 60% train, 20% validation, and 20% test. Exact counts depend on groups. Every split must contain both classes.
3. **Prepare faces.** Decode each video once in order and retrieve 12 uniformly spaced frames, detect a dominant face, add a margin, and cache 224x224 JPEG crops. Reject frames with two similarly large faces. A clip needs at least four usable frames. Failures are recorded, not assigned invented scores.
4. **Extract features once per encoder.** Use the encoder's official ImageNet normalization and inference mode. Subsequent classifier experiments reuse the vectors.
5. **Train the classifier.** Fit scaling statistics on training data only. Each video receives equal total weight within its class, then classes are balanced. Try C = 0.01, 0.1, 1, and 10. Average frame scores into one score per video.
6. **Select on validation.** Choose the threshold using validation balanced accuracy. Rank classifier/encoder candidates by validation balanced accuracy, then AUC, then smaller C. An exact tie between encoders follows the configured order.
7. **Evaluate the selected model.** Freeze selection before looking at the test metrics. Report video accuracy, balanced accuracy, AUC, fake precision/recall/F1, log loss, confusion matrix, majority-class baseline, analysis coverage, and source-group bootstrap intervals. Bootstrap intervals from this small sample remain uncertain.

Default settings are in `ml/configs/baseline.json`. Each saved run records settings, package versions, dataset/feature fingerprints, model version, checkpoint size, and SHA-256. Feature caches invalidate when relevant package versions change. Checkpoints contain tensors and plain metadata and load with `weights_only=True`.

## Outputs and reading the code

All generated outputs live in ignored `data/`:

| Folder | Contents |
| --- | --- |
| `assets/` | Verified YuNet model and ImageNet weights |
| `manifests/` | Labels, source references, hashes, fixed splits |
| `crops/dfdc_sample/` | Face images and per-video audit files |
| `features/dfdc_sample/` | NumPy vectors and cache provenance |
| `review/` | Training crop sheet and CPU timing report |
| `runs/cpu_baseline/` | Selected `model.pt`, validation comparison, test metrics, predictions, and plot |

The code follows the same order: `data.py` -> `faces.py` -> `features.py` -> `train.py` -> `evaluate.py`. `predict.py` loads the saved encoder and classifier for a new video. `__main__.py` connects the commands; it contains no hidden training service or AutoML framework.

No dataset clips, face crops, checkpoints, or credentials belong in Git. The GitHub branch contains the code and setup instructions. A downloaded ImageNet encoder is not a trained deepfake model; a real run must create `model.pt` and its measured evaluation report before claiming baseline results.

## Limits and next steps

DFDC labels can include face swaps, voice swaps, or both. A face-only system may miss a voice-only fake. Original-video grouping does not prove actor-disjoint or session-disjoint splits because verified actor identities are not supplied here. A 400-video sample also cannot establish performance on banking KYC recordings, new manipulation methods, or different compression.

Scores are experimental visual classifier outputs, not calibrated probabilities of fraud. Insufficient faces produce `insufficient_evidence`. Audio analysis, temporal modeling, Grad-CAM, signing, and frontend/backend integration remain separate milestones. No banking eligibility decision should be automated from this baseline.

Next, retain this experiment as the CPU reference, obtain FaceForensics++ access, and use the university GPU for controlled fine-tuning and larger independent evaluation. Compare methods using fixed splits and validation decisions; report final tests without changing settings to improve those test scores.

Primary references: [EfficientNet-B0](https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.efficientnet_b0.html), [ResNet18](https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.resnet18.html), [OpenCV YuNet](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet), [DFDC official data](https://www.kaggle.com/competitions/deepfake-detection-challenge/data), [FaceForensics++ access](https://github.com/ondyari/FaceForensics/blob/master/dataset/README.md).
