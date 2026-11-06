# Deep Forensics frontend

A local React and Vite application for the Deep Forensics video verification project. It includes video selection and preview, five explicit demo scenarios, simulated processing, results, recent sessions, JSON export, and printable sample reports.

## Start on Windows

Double-click `START_FRONTEND.cmd` in the parent project folder. It installs missing dependencies, starts the development server, and opens the browser. Keep the terminal open while using the application. Press Ctrl+C in that terminal to stop it.

Alternatively, run:

```powershell
cd "C:\Users\hp\Desktop\Deep Forsencis\frontend"
npm install
npm run dev
```

Open the local URL printed in the terminal, normally http://127.0.0.1:5173. If that port is occupied, Vite prints another available port. Once dependencies are installed, `npm run dev` is sufficient for later sessions.

Use Node.js 20.19+ or 22.12+ as required by this Vite version. This computer had Node.js 22.16.0 when the project was created. The lockfile records the resolved dependencies.

## Try the complete workflow

1. Choose an MP4 up to 50 MB and wait for its browser preview, or click **Try an example** with no video.
2. Choose a sample scenario in Analysis setup: high risk, needs review, low risk, insufficient evidence, or processing error.
3. Start the demo and watch the simulated stages.
4. Review the sample visual result and the unavailable audio/evidence states.
5. Use **View sample report**, then **Print / Save PDF**, or **Export JSON**.
6. Open **Recent sessions** to revisit the last 20 records in this browser tab. Videos are not stored. Clearing the history removes those local records.

No dataset or Python backend is needed for Demo mode. No model inference occurs. Scores are fixed fixtures and do not describe the selected video. Audio analysis, Grad-CAM generation, SHA-256 calculation, digital signatures, and protected audit logging are not implemented.

## Check the project

```powershell
npm test
npm run build
npm run preview
```

The tests cover unusable uploads, missing audio, demo stage progression, insufficient evidence, failures, aborted requests, live API errors, invalid API results, and damaged browser storage. The production output is in dist/. Use the preview URL printed in the terminal to inspect it locally.

## Main files

| File or folder | Purpose |
| --- | --- |
| src/App.jsx | Screen navigation, upload state, polling, and browser history |
| src/pages/ | Upload, processing, results, and recent-session screens |
| src/components/ | Shared layout, uploader, evidence gallery, dialogs, and report |
| src/mocks/analyses.js | Fixed sample scenarios and processing stages |
| src/services/analysisService.js | Mock and live API implementations |
| src/lib/utils.js | Validation, result checks, formatting, and storage helpers |
| src/styles.css | Responsive layout and report print styles |

## Connect FastAPI later

Copy .env.example to .env.local and change:

```dotenv
VITE_USE_MOCKS=false
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Restart Vite after changing environment variables. These frontend settings are public configuration, not secret storage. Demo mode is the default when VITE_USE_MOCKS is omitted. Setting the literal string false selects the live service; live API failures never silently fall back to demo predictions.

The backend must allow the frontend development origin through CORS, for example http://127.0.0.1:5173. Adjust this if Vite prints a different port. The expected endpoints are:

| Endpoint | Request and response |
| --- | --- |
| POST /api/analyses | Multipart field file; returns a string id and status queued |
| GET /api/analyses/{id} | Returns id, scope, status, stage, and completed results |
| GET /api/analyses/{id}/report | Returns a PDF when report_available is true |

Supported statuses are queued, running, complete, failed, and insufficient_evidence. Known stage identifiers are queued, validating, extracting, analyzing, and reporting. Unknown running stages use a generic processing label. The frontend stops polling on completion, failure, insufficient evidence, or navigation away. Returning to upload stops monitoring; it does not cancel a real server job.

Example completed response:

```json
{
  "id": "analysis-001",
  "status": "complete",
  "stage": "complete",
  "scope": "visual_only",
  "created_at": "2026-11-05T12:00:00Z",
  "visual": {
    "status": "complete",
    "score": 0.72,
    "verdict": "FAKE",
    "model_version": "your-trained-model-version"
  },
  "audio": { "status": "not_implemented", "score": null },
  "evidence": [],
  "sha256": null,
  "report_available": false
}
```

The numbers above illustrate the API schema, not measured model performance. The backend chooses thresholds and returns the verdict. The frontend validates a completed visual result instead of inventing a missing verdict. Error results should provide error or reason as a readable string. Missing source metadata is filled from the current upload.

Evidence entries can provide id, image_url, caption, kind, and timestamp in seconds. Use absolute HTTP(S) image URLs accessible to the browser; kind may be grad_cam or frame. Grad-CAM images should be described as attribution rather than proof of exact manipulation boundaries. A backend report button appears only when report_available is true in live mode.

The browser report is an unsigned summary. It must not be represented as a signed forensic audit report. Recent sessions use sessionStorage and provide no protected chain of custody.
