# Local integration verification — 6 November 2026

The backend was checked against the existing `visual-baseline-bb68915008` checkpoint. No training, test-set tuning, threshold change, or modification to `ml/predict.py` was made.

## Automated checks

- **21 backend tests passed:** upload contents/type/size checks, streamed-body limits, decoded duration/FPS/resolution limits, queue capacity and serial execution, success/insufficient-evidence/error/timeout responses, deletion, original-file preservation, safe cleanup scope, readiness checks, allowed origins/hosts, bounded history, and restart behavior.
- **18 existing ML tests passed**, together with the backend tests (`39 passed`).
- **14 frontend tests passed**, including live mode selection, health checks, upload metadata limits, API failures, insufficient evidence, and preserved demo behavior.
- Both `npm run build` and `npm run build:live` passed.
- `pip check` reported no broken requirements. Starlette emits a deprecation warning for its currently supported HTTPX test-client adapter; this does not affect the running app.

## Real checkpoint and HTTP check

A known **training** clip was sent through the running HTTP upload endpoint. Its returned video score, threshold, verdict, model version, and all frame scores matched the previously verified direct prediction exactly. It provided 12 usable frames from 12 sampled frames. The timed API job took 27.33 seconds in that run, including process startup, decoding, model loading, prediction, and cleanup; this is a single-run observation, not a speed guarantee.

A generated blank MP4 returned `insufficient_evidence` with no visual score. A renamed non-video was rejected with HTTP 415. An MP4-like header with corrupted contents reached the worker and returned `failed`. All three accepted test jobs confirmed deletion of their backend copies, and the server upload directory contained no remaining job files.

These checks establish software integration and parity with the saved model. They do **not** measure accuracy on new unseen videos. The original held-out metrics remain in [the baseline experiment](../ml/experiments/dfdc_sample_cpu_2026-11-06.md).

## Browser check

The connected frontend at `http://127.0.0.1:8000` was exercised through the actual file chooser: preview, Start analysis, processing, and completed result. It displayed Local model mode, the actual score and verdict, 12/12 usable frames, the 66.34% displayed decision threshold, unavailable audio/evidence images, and deletion confirmation. The printable summary showed the same values. The record survived a page reload in Recent sessions, and the final built interface reopened it correctly.

The QA video, screenshot, detailed inference output, model checkpoint, and generated builds stay local and are excluded from Git.
