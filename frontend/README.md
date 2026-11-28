# Deep Forensics frontend

A React and Vite interface for local visual and audio deepfake screening. The command overview opens the verification workstation. The connected app runs the trained Python models and displays separate channel results; the separate demo retains five fixed scenarios. Both offer video preview, results, recent sessions, JSON export, and printable summaries.

## Run the connected model

From the project root in PowerShell, run `cd frontend; npm run build:live; cd ..`, then `.\.venv\Scripts\python.exe -m backend`. This builds the live interface and serves it with the Python backend at http://127.0.0.1:8000. No frontend environment edits are needed. Confirm **Local model ready**, select an MP4, and click **Start analysis**. This uses the real local checkpoint. See the [complete guide](../backend/README.md).

Live uploads are limited to 50 MiB, 60 seconds, 60 FPS, and 4K; 1080p is recommended. Results display actual frame coverage, separate channel scores and thresholds when available, model versions, and upload cleanup status. The selected source file gets a browser-only SHA-256 fingerprint before analysis. It is not a server-side evidence seal and is not included in the analysis report. The models remain experimental. Calibrated fusion, Grad-CAM images, server-side upload hashing, and digital signatures remain unavailable.

## Start the separate demo on Windows

From the project root, run `cd frontend`, `npm ci`, set `$env:VITE_USE_MOCKS = "true"`, then run `npm run dev -- --open`. This starts the separate demo and opens the browser. Keep the terminal open while using the application. Press Ctrl+C in that terminal to stop it.

Alternatively, run:

```powershell
cd frontend
npm ci
$env:VITE_USE_MOCKS = "true"
npm run dev -- --open
```

Open the local URL printed in the terminal, normally http://127.0.0.1:5173. If that port is occupied, Vite prints another available port. Once dependencies are installed, `npm run dev -- --open` is sufficient for later sessions.

Use Node.js 20.19+ or 22.12+ as required by this Vite version. This computer had Node.js 22.16.0 when the project was created. The lockfile records the resolved dependencies.

## Try the complete workflow

1. Open **Live workstation** from the overview. Choose an MP4 up to 50 MB and wait for its browser preview and fingerprint, or click **Try an example** with no video.
2. Choose a sample scenario in Analysis setup: high risk, needs review, low risk, insufficient evidence, or processing error.
3. Start the demo and watch the simulated stages.
4. Review the sample visual result and the unavailable audio/evidence states.
5. Use **View sample report**, then **Print / Save PDF**, or **Export JSON**.
6. Open **Recent sessions** to revisit the last 20 records in this browser tab. Videos are not stored. Clearing the history removes those local records.

## Process multiple videos

Open **Batch processing** in the sidebar, select or drop up to 10 MP4 files, and click **Start batch**. Each file has its own status and result. Invalid files are marked before upload; a failed file does not stop the remaining queue. Open an individual result for its visual and audio findings, or export the completed batch results as JSON. In demo mode all videos use the selected sample scenario and no model runs.

In connected mode the browser keeps at most two submissions in flight and waits when the backend queue is full. The backend still runs one CPU inference job at a time and accepts up to three active jobs. This improves upload overlap and operator workflow, but does not increase model inference speed. Elapsed time appears beside completed live jobs. Uploaded backend copies are deleted after each analysis; original files stay on the user's computer. Batch state stays in the open browser page and is lost on reload; completed metadata is also added to Recent sessions.

No dataset or Python backend is needed for Demo mode. No model inference occurs. Scores are fixed fixtures and do not describe the selected video. Demo audio stays unavailable; the connected app can run the trained audio model. Browser SHA-256 calculation is available for a selected file. Grad-CAM generation, backend evidence sealing, digital signatures, and protected audit logging are not implemented.

## Check the project

```powershell
npm test
npm run build
npm run build:live
npm run preview
```

The tests cover unusable uploads, missing audio, demo stage progression, insufficient evidence, failures, aborted requests, live API errors, invalid API results, and damaged browser storage. The production output is in dist/. Use the preview URL printed in the terminal to inspect it locally.

## Main files

| File or folder | Purpose |
| --- | --- |
| src/App.jsx | Screen navigation, upload state, polling, and browser history |
| src/pages/ | Overview, upload, processing, results, and recent-session screens |
| src/components/ | Shared layout, uploader, dual-stream inspector, dialogs, and report |
| src/mocks/analyses.js | Fixed sample scenarios and processing stages |
| src/services/analysisService.js | Mock and live API implementations |
| src/lib/utils.js | Validation, result checks, formatting, and storage helpers |
| src/styles.css | Existing layout and report print styles used by all screens |
| src/command-center.css | Dark command-center theme and motion |

`node_modules/`, `dist/`, and `dist-live/` are generated locally and ignored by Git. Keep `node_modules/` to run Vite without reinstalling packages. Keep or regenerate `dist-live/` with `npm run build:live` to serve the connected app.

## Frontend development with the live backend

For hot reload alongside the running Python backend, copy .env.example to .env.local and change:

```dotenv
VITE_USE_MOCKS=false
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Restart Vite after changing environment variables. These frontend settings are public configuration, not secret storage. Demo mode is the default when VITE_USE_MOCKS is omitted. Setting the literal string false selects the live service; live API failures never silently fall back to demo predictions.

The backend allows localhost and 127.0.0.1 on development port 5173 through CORS. Keep Vite on this port or adjust the explicit backend allowlist. The API is:

| Endpoint | Request and response |
| --- | --- |
| GET /api/health | Model readiness and version |
| POST /api/analyses | Multipart field file; returns a string id and status queued |
| GET /api/analyses/{id} | Returns id, scope, status, stage, and completed results |
| GET /api/analyses/{id}/report | Reserved for later; currently unavailable and report_available is false |

The live build uses same-origin API requests and is separate from the default demo build. Supported statuses are queued, running, complete, failed, and insufficient_evidence. Demo stages are queued, validating, extracting, analyzing, and reporting. The actual backend uses queued and analyzing, with validation, face extraction, and prediction grouped under analyzing. Unknown running stages use a generic processing label. The frontend stops polling on completion, failure, insufficient evidence, or navigation away. Returning to upload stops monitoring; it does not cancel a real server job.

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

The numbers above illustrate a visual-only API response, not measured model performance. With usable audio, the backend also returns an `audio` score, verdict, threshold, and model version and sets `scope` to `multimodal`. These remain separate channel verdicts; no final combined verdict is calibrated. The frontend validates measured results instead of inventing a missing verdict. Error results should provide error or reason as a readable string. Missing source metadata is filled from the current upload.

Evidence entries can provide id, image_url, caption, kind, and timestamp in seconds. The new inspector accepts same-origin paths or inline PNG/JPEG/WebP images. The current backend does not provide frame or spectrogram images. Grad-CAM images, if added later, should be described as attribution rather than proof of exact manipulation boundaries. A backend report button appears only when report_available is true in live mode.

The browser report is an unsigned summary. It must not be represented as a signed forensic audit report. Recent sessions use sessionStorage and provide no protected chain of custody.
