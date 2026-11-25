DEEP FORENSICS - START HERE
===========================

This local research prototype checks visual and audio signals in recorded
video verification clips. It shows separate model results. The scores do not
prove fraud or identity; a validated combined decision is future work.

RUN THE REAL APP ON THIS LAPTOP
-------------------------------
Double-click START_APP.cmd in this folder. It checks the installed models,
builds the live frontend, and opens the connected app. Keep its window open.

If that local start file is missing, open PowerShell in this project folder
and enter:

  cd frontend
  npm run build:live
  cd ..
  .\.venv\Scripts\python.exe -m backend --check
  .\.venv\Scripts\python.exe -m backend

The browser should open at http://127.0.0.1:8000. Check for "Local model
ready", choose a short MP4, and select "Start analysis". Keep PowerShell open
while using the app; press Ctrl+C to stop it. The backend deletes its
temporary uploaded copy after analysis. Your original video stays in place.

ONE-TIME SETUP ON A NEW COMPUTER
--------------------------------
Install a supported Python version and Node.js. From this folder in
PowerShell, run:

  python -m venv .venv
  .\.venv\Scripts\python.exe -m pip install -r ml\requirements-torch-cpu.txt
  .\.venv\Scripts\python.exe -m pip install -r ml\requirements-lock.txt
  .\.venv\Scripts\python.exe -m ml setup-assets
  .\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
  .\.venv\Scripts\python.exe -m pip install -r audio\requirements.txt
  cd frontend
  npm ci
  cd ..

Setup installs packages and the face detector. It does not train a deepfake
model. Copy model.pt and training_summary.json from the training computer to
data\runs\cpu_baseline\. For audio, copy model.joblib and training_summary.json
to data\runs\audio_baseline\. Model weights and datasets are not on GitHub.
See backend\README.md for troubleshooting.

OTHER COMMANDS (RUN FROM THE PROJECT FOLDER)
--------------------------------------------
Visual prediction on one video:
  .\.venv\Scripts\python.exe -m ml predict --video "C:\path\to\video.mp4"

Train the visual baseline with the labeled DFDC sample:
  .\.venv\Scripts\python.exe -m ml run --source "C:\path\to\train_sample_videos.zip"

Start the separate interface demo (fixed sample scores, no model analysis):
  Double-click START_FRONTEND.cmd on this laptop, or run:
  cd frontend
  $env:VITE_USE_MOCKS = "true"
  npm run dev -- --open

The demo setting applies to this PowerShell window. Open a new PowerShell
window in the project folder to run the real app again.

WHERE THINGS ARE
----------------
frontend\           React interface (JavaScript and CSS).
backend\            Python service for uploads and model inference.
ml\                 Visual model training, evaluation, and prediction.
audio\              Audio model training, evaluation, and prediction.
data\               Local datasets and model files; excluded from Git.
docs\               Proposal checklist and local reference documents.

For technical details, open backend\README.md, ml\README.md, and
audio\README.md in a Markdown viewer such as GitHub or VS Code. This file is
plain text and opens cleanly in Windows Notepad.

CURRENT LIMITS
--------------
- The visual model can falsely label a real clip as fake, especially on
  unfamiliar or compressed video.
- The original audio baseline remains active. A tested robustness candidate
  raised genuine-audio false alarms and was not activated.
- Visual and audio results are not yet fused into a validated final verdict.
- Do not use these experimental results to approve or deny a bank customer.

The remaining proposal work is in docs\proposal_alignment_2026-11-09.md.
