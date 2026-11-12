# Connected local application

The React frontend sends real videos to a Python FastAPI backend. It runs the trained visual checkpoint and, when installed, the separate ASVspoof 2019 LA audio checkpoint. The two scores are shown separately; there is no fused fraud score.

## Run it on Windows

1. Double-click **START_APP.cmd** in the project folder.
2. Wait for the browser to open at **http://127.0.0.1:8000**. Keep the app's terminal window open.
3. Confirm the page says **Local model ready**. The audio card shows a score only for a video with usable audio and a valid local audio checkpoint.
4. Click **Choose video**, select an MP4, and wait for the preview.
5. Click **Start analysis**. Review the visual and audio results, usable frame count, model versions, and decision thresholds.
6. Use **View summary** to print/save an unsigned PDF, or **Export JSON** for the full prediction, including frame scores.
7. Press **Ctrl+C** in the app's terminal to stop it. An active prediction may finish before shutdown.

The packages have already been installed on the development laptop. On another checkout, first run **SETUP_BASELINE.cmd**, restore or train the visual baseline, and run **SETUP_APP.cmd** once. `SETUP_APP.cmd` also installs the audio decoder dependencies. The local visual checkpoint, its training summary, and `data/assets/` detector files are required. The audio checkpoint under `data/runs/audio_baseline/` is optional; train or restore it using [audio instructions](../audio/README.md). GitHub does not contain model weights. Setup does not retrain a model.

**START_FRONTEND.cmd** remains the separate frontend demonstration/development launcher. Its default demo scores are fixed examples. **START_APP.cmd** builds a separate live frontend in `frontend/dist-live/`, overriding demo configuration for that build, then serves both UI and API from one local address. It needs no `.env.local` edits. Reopening it rebuilds the frontend from the current source.

## What happens after an upload

The audio run can be selected using `python -m audio activate --run data/runs/<run-name>` with the project's Python environment. Restart the app after activation. A checksum-verified local pointer selects that run; an alternative also requires a matching approved release decision. The candidate reported on 12 November did not pass that check. Without a pointer, the original audio baseline is used. An invalid pointer produces an explicit startup error. See [audio model selection and rollback](../audio/ROBUSTNESS.md).

```text
React upload page
    -> POST /api/analyses (one MP4)
    -> bounded queue, one CPU job at a time
    -> check duration/resolution and decode the video
    -> ml.predict.predict_video using the saved ResNet18 checkpoint
    -> audio.predict.predict_video_audio using the saved audio checkpoint, when present
    -> delete the backend's video copy
    -> GET /api/analyses/{id} returns the actual result
    -> React displays the result and offers JSON/print export
```

- **React / JavaScript / CSS:** the existing interface, preview, polling, history, and reports.
- **Python / FastAPI / Uvicorn:** file uploads, job status, local HTTP service, and serving the built frontend. See the official [FastAPI upload documentation](https://fastapi.tiangolo.com/tutorial/request-files/) and [Uvicorn settings](https://uvicorn.dev/settings/).
- **OpenCV and PyTorch:** the existing face detector and frozen ResNet18 encoder with trained logistic classifier. The worker calls the same `ml/predict.py` function as **PREDICT_VIDEO.cmd**. Its checkpoint and threshold are unchanged.
- **SoundFile, FFmpeg, NumPy, scikit-learn:** extract the MP4 speech and score it with the CPU log-mel audio classifier. The audio checkpoint and its validation-selected threshold are separate from the visual model.
- **A Python subprocess per video:** isolates decoding and prediction, with a 180-second timeout. Only one worker runs inference at a time, limiting memory use on this CPU laptop. This adds model-loading time to each request.

No database, cloud upload, GPU, Docker, account login, or paid service is required. This is a single-user local prototype, not a public deployment.

## Limits and interpretation

Use an MP4 up to **50 MiB**, **60 seconds**, **60 FPS**, and **4K** (at most 3840 × 2160 pixels in either orientation; neither edge above 4096). Use 1080p and a short clip with one clearly visible face for a quicker first test. The frontend checks size/duration/resolution, and the backend independently checks file contents and decoded metadata. The server accepts at most three active uploads/jobs, processing them serially. Extra requests receive a readable queue-full error.

The visual baseline samples up to 12 frames and requires at least four usable face crops. **Insufficient visual evidence** has no visual verdict or score, though a usable audio track may still yield a separate audio signal. An unreadable video, timeout, or missing visual model is an error, never a fake result or an automatic demo fallback.

**REAL and FAKE are experimental model predictions.** Neither score is a calibrated probability of manipulation, identity fraud, or bank eligibility. False alarms and missed fakes remain possible. The visual model's [baseline report](../ml/experiments/dfdc_sample_cpu_2026-11-06.md) and [external-video diagnostic](../ml/experiments/external_video_44639_2026-11-06.md) describe its limits. The [audio robustness report](../audio/experiments/asvspoof2019_la_robustness_2026-11-12.md) includes an independent official-data subset; the new candidate was not activated because its genuine false alarms increased. Representative compressed banking-video evaluation is still needed. Connecting models does not improve their measured accuracy.

Audio detection is available when its trained local artifact is present. A missing or unusable audio track yields no audio score. Grad-CAM images, uploaded-video hashing, digital signatures, and protected audit logging remain unavailable. Browser reports are unsigned summaries, not certified forensic reports.

## Storage and cleanup

The server assigns a random job ID and stores its temporary upload below `data/backend/temporary/server-.../DF-.../video.mp4`. The supplied filename is only display metadata, never a storage path. Normal completion, insufficient evidence, prediction failure, rejection, and timeout all clean up the owned job directory. Results become visible only after cleanup is attempted, and `upload_deleted` reports whether it succeeded. A cleanup failure is shown explicitly in the UI.

The selected original video on your computer is never deleted. The browser may retain its preview while the page is open. Up to 100 completed results remain in server memory until restart; the last 20 viewed results remain in this tab's session storage. Export JSON if you need a lasting result. Closing/restarting the backend loses job lookup history. Leaving the processing screen stops polling, but the server completes and cleans up its job.

A forced process kill or power loss can leave a temporary directory behind. After stopping the app, check `data/backend/temporary/` if this happens. The server deliberately does not recursively delete other server instances' directories. None of the videos, temporary files, checkpoints, or generated builds are committed to Git.

## Files to understand first

| File | Responsibility |
| --- | --- |
| `backend/app.py` | Upload validation, readiness, CORS, API routes, frontend hosting |
| `backend/jobs.py` | Bounded queue, one CPU worker, timeout, cleanup, result storage |
| `backend/worker.py` | Decoded-video checks and calling the existing predictor |
| `backend/config.py` | Local paths and resource limits |
| `backend/__main__.py` | Startup checks, local port, browser opening |
| `frontend/src/services/analysisService.js` | Frontend health check, upload, status polling |
| `ml/predict.py` | Existing trained inference pipeline, unchanged by this integration |
| `audio/predict.py` | MP4 speech extraction and trained audio score |

## API and development

| Endpoint | Behavior |
| --- | --- |
| `GET /api/health` | Ready state, model version, limits, retention policy |
| `POST /api/analyses` | Multipart field `file`; HTTP 202 with job ID |
| `GET /api/analyses/{id}` | Queued/running/complete/failed/insufficient_evidence result |
| `GET /docs` | FastAPI's local API documentation |

There is no server PDF endpoint; `report_available` is false. The existing browser print/JSON exports work with real results. Stages in live mode are `queued` and `analyzing`; the latter includes decoding, face extraction, and inference rather than simulated timed steps.

Start the backend with `.venv/Scripts/python.exe -m backend --no-browser` after `npm run build:live` in `frontend/`. For frontend hot reload, run the backend, set `VITE_USE_MOCKS=false` and `VITE_API_BASE_URL=http://127.0.0.1:8000` in an ignored `frontend/.env.local`, and run `npm run dev`. Development CORS allows localhost/127.0.0.1 on port 5173; use that port or deliberately adjust the allowlist. Foreign browser origins and unexpected Host headers are rejected. Bind to loopback and use **one server worker**; the job store is in memory.

```powershell
.venv/Scripts/python.exe -m pytest audio/tests backend/tests ml/tests -q
.venv/Scripts/python.exe -m pip check
cd frontend
npm test
npm run build
npm run build:live
```

## Troubleshooting

- **Package missing:** run SETUP_APP.cmd. If the baseline packages/checkpoint are missing, follow `ml/README.md` first.
- **Model unavailable:** restore the checkpoint, training summary, and verified face detector; the backend checks their hashes. Restart after restoring them.
- **Port 8000 in use:** close the previous app terminal gracefully, then run START_APP.cmd again. Do not stop unrelated programs blindly.
- **Browser did not open:** open http://127.0.0.1:8000 manually while the app terminal is running.
- **Video preview fails:** use a browser-compatible H.264 MP4.
- **Insufficient evidence:** use a clear face, sufficient lighting, and one prominent subject. It is not a REAL verdict.
- **A real video is flagged:** keep it as a diagnostic; do not change the model threshold based on one uploaded clip. The original baseline is intentionally preserved.
