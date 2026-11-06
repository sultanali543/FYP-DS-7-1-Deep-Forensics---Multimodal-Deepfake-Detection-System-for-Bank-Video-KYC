@echo off
setlocal DisableDelayedExpansion
title Deep Forensics - Visual baseline training
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing_setup
set "dataset_source=%~1"
if defined dataset_source goto run_training
set /p "dataset_source=Paste the path to the labeled DFDC sample ZIP or folder: "
set "dataset_source=%dataset_source:"=%"
if not defined dataset_source goto missing_source
:run_training
".venv\Scripts\python.exe" -m ml run --source "%dataset_source%"
if errorlevel 1 goto failed
echo Training and evaluation finished. Results are in data\runs\cpu_baseline.
pause
exit /b 0
:missing_setup
echo Run SETUP_BASELINE.cmd first.
pause
exit /b 1
:missing_source
echo A labeled dataset ZIP or folder path is required.
pause
exit /b 1
:failed
echo The baseline stopped. Read the error above. Existing crops and features are kept for resuming.
pause
exit /b 1
