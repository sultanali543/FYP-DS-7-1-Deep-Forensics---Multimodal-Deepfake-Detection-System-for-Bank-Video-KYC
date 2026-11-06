# Deep Forensics

A research prototype for reviewing recorded video verification sessions for visual manipulation, with a planned audio spoof detection pipeline and combined reporting workflow.

## Current implementation

The React frontend supports MP4 selection and preview, five explicit demonstration scenarios, simulated processing, visual result screens, recent sessions, JSON export, and printable sample reports. Demo scores are fixed fixtures and do not describe the uploaded video.

The Python visual baseline under `ml/` imports the labeled DFDC training sample, prepares face crops, compares frozen EfficientNet-B0 and ResNet18 features with trained logistic classifiers, and evaluates a selected checkpoint. Dataset-dependent results require a completed training run; pretrained ImageNet weights alone are not a deepfake detector.

The [first completed CPU baseline experiment](ml/experiments/dfdc_sample_cpu_2026-11-06.md) selected ResNet18 and scored 91.1% accuracy, 84.3% balanced accuracy, and 0.892 AUC on 79 analyzable held-out DFDC sample videos. The report includes coverage, error counts, uncertainty, and limitations. The trained checkpoint is local and excluded from Git.

The FastAPI backend, frontend connection to real inference, audio detection, Grad-CAM generation, uploaded-video hashing, digital signing, and protected audit logging are planned milestones.

## Run the visual baseline

On Windows, run **SETUP_BASELINE.cmd**, then **TRAIN_BASELINE.cmd** and supply the path to the official DFDC labeled training ZIP. The workflow reads one archived video at a time to avoid a second full dataset extraction. After training, **PREDICT_VIDEO.cmd** analyzes a new clip.

See [baseline setup, model rationale, and evaluation](ml/README.md) for the steps, limitations, and outputs. The frontend remains explicitly in demo mode until a backend connects it to the trained model.

## Run the frontend

On Windows, double-click START_FRONTEND.cmd. It installs missing frontend dependencies and opens the local development server.

Alternatively:

```powershell
cd frontend
npm install
npm run dev
```

See [frontend setup](frontend/README.md) for environment configuration and the expected API contract.

## Verify the frontend

```powershell
cd frontend
npm test
npm run build
```

## Development workflow

Work is organized on feature branches. See [Git workflow](GIT_WORKFLOW.md) and [project working instructions](AGENTS.md).

Dataset videos, uploaded media, model weights, local secrets, and generated dependencies are excluded from version control. Keep large training artifacts in the chosen cloud storage.
