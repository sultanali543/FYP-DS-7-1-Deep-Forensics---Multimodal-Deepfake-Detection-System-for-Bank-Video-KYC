# Deep Forensics frontend build guide

Build a local React interface while the datasets and inference backend are being prepared. The first milestone is a complete browser demonstration: choose a video, preview it, move through sample processing stages, inspect a sample visual result, and print a sample report. All analysis output must carry a visible Demo mode label.

This guide follows the React, Vite, and plain CSS choices in the existing solo plan. It assumes you are working alone and learning as you build. Finish one stage and its completion check before adding the next.

## 1 Define the first version

Use three screens within one application. React state can switch between them initially; a routing library is optional later.

| Screen | Required behavior |
| --- | --- |
| Upload | Select or drop a video, validate it, preview it, and start the demonstration |
| Processing | Show sample processing stages, prevent duplicate submissions, and handle failure |
| Results | Show a sample visual verdict and score, audio availability, evidence state, and report action |

Keep these items for later: accounts and login, database history, live webcam capture, model training, actual inference, and production deployment. The frontend milestone does not depend on obtaining datasets.

The larger project is multimodal. This first frontend should show `Analysis scope: Visual prototype` and `Audio analysis: Not implemented`. An absent audio result has a null score and must never appear as a passed audio check.

## 2 Create and run the React project

Node.js v22.16.0 and npm 10.9.2 were available when this guide was prepared. The current Vite guide lists Node.js 20.19+ or 22.12+ as its baseline requirement; individual templates can require more. Follow any engine warning from the installed template.

Open the project folder in VS Code and use its terminal. Run each command separately:

```powershell
cd "C:\Users\hp\Desktop\Deep Forsencis"
npm create vite@latest frontend -- --template react
cd frontend
npm install
npm run dev
```

If npm asks to install create-vite, accept that installation. Follow any template prompts; select React and JavaScript if asked. Open the local address printed by Vite. Leave the terminal running while developing. To stop it, press Ctrl+C.

Do not run the scaffold command again after the frontend folder exists. To resume development, enter the frontend folder and run `npm run dev`.

Completion check: the initial Vite React page opens in the browser, and editing visible text in App.jsx updates that page.

Official setup reference: https://vite.dev/guide/

## 3 Create a small file structure

Keep Vite's package files and main.jsx. Create the following files as you implement their stage; empty imports will otherwise break the application.

```text
frontend/
  src/
    main.jsx
    App.jsx
    styles.css
    pages/
      UploadPage.jsx
      ProcessingPage.jsx
      ResultsPage.jsx
    components/
      AppLayout.jsx
      VideoUploader.jsx
      ProcessingSteps.jsx
      VerdictBadge.jsx
      ScoreCard.jsx
      EvidenceGallery.jsx
      ReportView.jsx
    services/
      analysisService.js
    mocks/
      analyses.js
  .env.example
```

App.jsx owns the current screen, chosen file, analysis ID, latest result, and errors. Child components receive data and callbacks through props. Start with local React state; a separate state management package is unnecessary for this scope.

Use one stylesheet initially. Import styles.css once and remove starter styles that conflict with the new layout.

## 4 Build the shared layout first

AppLayout contains the Deep Forensics name, the application content area, a visible Demo mode badge, and a brief scope label. Start with a desktop layout that also stacks cleanly on a narrow screen.

Suggested visual choices:

| Item | Starting choice |
| --- | --- |
| Background | Light slate, such as #F8FAFC |
| Cards | White with a subtle gray border |
| Main text | Dark slate, such as #0F172A |
| Primary action | Dark blue with white text |
| Verdicts | Text badges with green, amber, or red accents |
| Spacing | A consistent 8 px spacing scale |

Use readable labels and visible keyboard focus. Verdicts need written text as well as color. Every button should have an implemented action or a clear disabled state with a reason.

Completion check: the shared layout looks consistent around all three screens, even when their content is still simple text.

## 5 Build the upload screen

Implement in this order:

1. A labeled file input. Make this work before adding drag and drop.
2. Prototype restrictions: MP4, a nonempty file, and a chosen maximum size of 50 MB. State these limits beside the input. These are development choices, not measured system limits.
3. Selected file name and size.
4. A video element with playback controls using a local object URL.
5. A Remove or Replace action that clears the previous result and error state.
6. An Analyze demo button, enabled only when the selection is usable.
7. Drag and drop using the same validation function as the file picker.

Handle video metadata or playback errors with an actionable message. Browser validation is for user experience; the later backend must independently validate uploads. Revoke old object URLs when replacing the selected file or unmounting its preview.

During this stage, choosing a video only previews it in the browser. It does not produce a genuine analysis.

Completion check: a usable MP4 previews correctly; an empty, unsupported, or oversized selection shows a clear error; starting without a usable file is prevented.

## 6 Define sample results and the service boundary

Put fixed sample analysis objects in mocks/analyses.js. Include these scenarios:

- Completed sample REAL visual result.
- Completed sample SUSPICIOUS visual result.
- Completed sample FAKE visual result.
- Insufficient evidence because no usable face was found.
- Failed analysis.

Use an explicit demo scenario selector during development. Do not invent a score from the filename or imply that a random score came from the uploaded video.

Example completed result shape:

```json
{
  "id": "demo-001",
  "mode": "demo",
  "status": "complete",
  "stage": "complete",
  "scope": "visual_only",
  "visual": {
    "status": "complete",
    "score": 0.82,
    "verdict": "FAKE",
    "model_version": null
  },
  "audio": {
    "status": "not_implemented",
    "score": null
  },
  "evidence": [],
  "sha256": null,
  "report_available": false
}
```

The value 0.82 is a fixed sample score. Label it `Sample visual model score`, not accuracy or probability of identity fraud. The eventual backend owns verdict calculation and threshold configuration; React displays the returned verdict.

Expose these functions through services/analysisService.js:

```text
createAnalysis(file, options) -> { id, status }
getAnalysis(id)              -> current status, stage, and result when ready
getReportUrl(id)             -> backend report URL when available
```

Start with a mock implementation. Later, keep these function names and replace their internal behavior with API requests. Components should use this service instead of calling fetch directly.

Example environment configuration:

```dotenv
VITE_USE_MOCKS=true
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Store this template in .env.example and copy it to .env.local when implementing the configuration. Vite reads frontend variables through import.meta.env; restart the development server after changing environment files.

Environment values are strings. Parse the mode explicitly so that the string `false` does not enable mocks:

```javascript
const useMocks = import.meta.env.VITE_USE_MOCKS === 'true';
```

Official environment configuration reference: https://vite.dev/guide/env-and-mode

Completion check: each sample scenario can be selected deliberately, and every sample output is visibly labeled as a demonstration.

## 7 Build processing and application transitions

The user flow is:

```text
Upload -> Sample processing -> Results
                           -> Insufficient evidence
                           -> Failure with retry
```

Use stages such as Queued, Validating video, Extracting faces, Analyzing frames, and Preparing results. Timed stage transitions are acceptable in Demo mode when clearly presented as sample processing. Do not present an arbitrary timer as measured backend progress.

Disable duplicate submissions while a run is active. Clear old polling and timers when leaving a screen, selecting another file, or starting a new run. A delayed response from an old analysis must not overwrite a newer result.

Completion check: the complete flow works for success, failure, and insufficient evidence. A failure offers retry, and insufficient evidence never becomes a REAL result.

## 8 Build the results screen

Show the most useful information first:

1. A visible Demo mode label and the analysis scope.
2. Visual result badge: REAL, SUSPICIOUS, or FAKE for completed samples.
3. Sample visual model score with an explanation of its scale.
4. Audio status: Not implemented, with no numeric score.
5. Selected video information and analysis ID.
6. Evidence gallery or an honest empty state.
7. A report action and an Analyze another video action.

For failure or insufficient evidence, show the reason and next action instead of an authenticity verdict. If no heatmaps exist, say `Heatmaps will appear after the explainability service is connected`. Do not label an ordinary video frame as a generated Grad-CAM heatmap.

Use sample evidence only when you have an appropriate asset, and mark it as sample evidence. Do not show invented hashes, model versions, inference times, or validation accuracy.

Completion check: all scenarios render without errors, missing values have useful labels, and starting a new analysis clears the old state.

## 9 Add a printable sample report

Create ReportView using the same result object displayed on the results screen. Include the project name, analysis ID, file name, visual score and verdict, audio status, evidence availability, and a prominent `Sample report — no model inference performed` statement.

Use a `Print / Save PDF` action that calls window.print(). Add print CSS to hide navigation and buttons and keep the report readable on white paper. This opens the browser print dialog, where the user can choose Save as PDF. It does not automatically download a generated backend PDF.

Show unavailable hashes and signatures as unavailable. A formal generated or digitally signed report is a later backend feature.

Completion check: the print preview is readable and agrees with the on-screen sample result.

## 10 Check the complete frontend

| Check | Expected result |
| --- | --- |
| Initial load | Useful upload screen, visible Demo mode, no console errors |
| Analyze with no file | Action disabled |
| Valid MP4 | Local preview and selected file details |
| Invalid or oversized file | Clear error and a way to choose another file |
| Replace a file | Old preview, result, and errors cleared |
| All three completed sample verdicts | Correct badge, sample score, and scope |
| No usable face | Insufficient evidence, with no REAL verdict |
| Simulated failure | Failure message and retry |
| Missing audio | Not implemented, null score |
| Missing heatmaps | Honest evidence empty state |
| Repeated clicks or navigation | No duplicate run or stale result |
| Analyze another video | Returns to a usable upload screen |
| Narrow browser window | No horizontal overflow; controls remain usable |
| Keyboard navigation | File input and buttons reachable with visible focus |
| Print preview | Sample report is readable and matches the screen |

Stop the development server if needed and run:

```powershell
npm run build
npm run preview
```

The first command creates the production build. The second serves it locally for a final check; use the address printed in the terminal. A working development server alone is not the completion check.

## 11 Connect real inference after the backend exists

Dataset availability does not automatically make the backend ready. Continue using Demo mode until an actual inference endpoint returns results.

Agree these endpoints with the backend implementation:

| Endpoint | Contract |
| --- | --- |
| POST /api/analyses | Accept multipart video upload and return a job ID |
| GET /api/analyses/{id} | Return status, stage, failure reason, and completed result |
| GET /api/analyses/{id}/report | Return a real report when available |

Then update analysisService.js to send FormData and poll the job endpoint. Let the browser set the multipart boundary; do not manually set a multipart Content-Type header. Handle non-success responses, network errors, and backend unavailability. Stop polling on completion, failure, insufficient evidence, or navigation away.

Set VITE_USE_MOCKS=false only for the real API path. Never silently fall back to sample scores when the API fails. A development demo can remain available as an explicit separate mode.

If the backend is visual-only, retain the Visual only scope and the unavailable audio state. Datasets, model training, and audio integration remain separate milestones.

## Suggested working order while working alone

First session: setup, shared layout, and a working file preview. Second session: fixtures, processing stages, and results. Third session: sample report, error cases, responsive layout, and production build. The time needed depends on your React experience; use the completion checks instead of treating these sessions as guaranteed deadlines.

Your immediate next action is Stage 2. Once the starter runs, build the shared layout and upload preview before adding any result cards.
