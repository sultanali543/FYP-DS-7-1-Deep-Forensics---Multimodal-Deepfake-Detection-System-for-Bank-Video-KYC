@echo off
setlocal
title Deep Forensics - Connected app setup
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing_baseline
where npm.cmd >nul 2>nul
if errorlevel 1 goto missing_node
echo Installing the backend packages into this project's existing environment.
".venv\Scripts\python.exe" -m pip install -r backend\requirements-dev.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r audio\requirements.txt
if errorlevel 1 goto failed
cd frontend
call npm.cmd ci
if errorlevel 1 goto failed
echo Setup complete. Run START_APP.cmd to use the connected model.
pause
exit /b 0
:missing_baseline
echo Run SETUP_BASELINE.cmd first. The connected app also needs your trained model in data\runs\cpu_baseline.
pause
exit /b 1
:missing_node
echo Install a supported Node.js LTS version, then retry.
pause
exit /b 1
:failed
echo Setup failed. Check the message above and your internet connection.
pause
exit /b 1
