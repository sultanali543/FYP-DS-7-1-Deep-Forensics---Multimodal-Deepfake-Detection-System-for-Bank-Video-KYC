# Deep Forensics

A research prototype for reviewing recorded video verification sessions for visual manipulation, with a planned audio spoof detection pipeline and combined reporting workflow.

## Current implementation

The React frontend is connected to a local Python FastAPI backend. Uploading an MP4 in the connected app runs the saved visual model and shows its actual result, frame coverage, threshold, and model version. It supports recent sessions, JSON export, and unsigned printable summaries. A separate demo mode retains clearly labeled fixed examples.

The Python visual baseline under `ml/` imports the labeled DFDC training sample, prepares face crops, compares frozen EfficientNet-B0 and ResNet18 features with trained logistic classifiers, and evaluates a selected checkpoint. Dataset-dependent results require a completed training run; pretrained ImageNet weights alone are not a deepfake detector.

The [first completed CPU baseline experiment](ml/experiments/dfdc_sample_cpu_2026-11-06.md) selected ResNet18 and scored 91.1% accuracy, 84.3% balanced accuracy, and 0.892 AUC on 79 analyzable held-out DFDC sample videos. The report includes coverage, error counts, uncertainty, and limitations. The trained checkpoint is local and excluded from Git.

Audio detection, Grad-CAM generation, uploaded-video hashing, digital signing, and protected audit logging remain planned milestones. The live visual baseline is experimental and can produce false alarms and missed fakes.

## Run the connected app

Double-click **START_APP.cmd**, wait for **http://127.0.0.1:8000** to open, and confirm **Local model ready**. Choose a short MP4, then click **Start analysis**. Keep the app terminal open; press Ctrl+C there to stop it. The backend deletes its uploaded copy after analysis, leaving your original untouched.

The packages and trained checkpoint are already available on the development laptop. For another checkout, run the baseline setup, restore/train the checkpoint, then run **SETUP_APP.cmd** once. GitHub contains the source, not the model weights. No new dataset or retraining is required to use the existing checkpoint.

See the [step-by-step run guide and backend explanation](backend/README.md) for limits, storage behavior, troubleshooting, and the API.

## Run the visual baseline

On Windows, run **SETUP_BASELINE.cmd**, then **TRAIN_BASELINE.cmd** and supply the path to the official DFDC labeled training ZIP. The workflow reads one archived video at a time to avoid a second full dataset extraction. After training, **PREDICT_VIDEO.cmd** analyzes a new clip.

See [baseline setup, model rationale, and evaluation](ml/README.md) for the steps, limitations, and outputs. The connected app uses that same predictor without changing the trained model or threshold.

## Run the separate frontend demo

On Windows, double-click START_FRONTEND.cmd. It installs missing frontend dependencies and opens the local development server.

Alternatively:

```powershell
cd frontend
npm install
npm run dev
```

See [frontend setup](frontend/README.md) for demo/live configuration and the implemented API contract.

## Verify the frontend

```powershell
cd frontend
npm test
npm run build
```

## Development workflow

Work is organized on feature branches. See [Git workflow](GIT_WORKFLOW.md) and [project working instructions](AGENTS.md).

Dataset videos, uploaded media, model weights, local secrets, and generated dependencies are excluded from version control. Keep large training artifacts in the chosen cloud storage.
