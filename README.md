# Deep Forensics

A research prototype for reviewing recorded video verification sessions for visual manipulation, with a planned audio spoof detection pipeline and combined reporting workflow.

## Current implementation

The React frontend supports MP4 selection and preview, five explicit demonstration scenarios, simulated processing, visual result screens, recent sessions, JSON export, and printable sample reports. Demo scores are fixed fixtures and do not describe the uploaded video.

Real model inference, the FastAPI backend, audio detection, Grad-CAM generation, SHA-256 calculation, digital signing, and protected audit logging are planned milestones.

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
