@echo off
setlocal DisableDelayedExpansion
title Deep Forensics - Visual baseline prediction
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing_setup
set "video_source=%~1"
if defined video_source goto run_prediction
set /p "video_source=Paste the path to an MP4 video: "
set "video_source=%video_source:"=%"
if not defined video_source goto missing_source
:run_prediction
".venv\Scripts\python.exe" -m ml predict --video "%video_source%"
set "prediction_status=%errorlevel%"
pause
exit /b %prediction_status%
:missing_setup
echo Run SETUP_BASELINE.cmd first.
pause
exit /b 1
:missing_source
echo An MP4 path is required.
pause
exit /b 1
