@echo off
setlocal
title Deep Forensics - Connected visual model
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing_setup
if not exist "frontend\node_modules\vite\bin\vite.js" goto missing_setup
where npm.cmd >nul 2>nul
if errorlevel 1 goto missing_setup
".venv\Scripts\python.exe" -m backend --check
if errorlevel 1 goto failed
echo Preparing the connected frontend. This does not train or change the model.
cd frontend
call npm.cmd run build:live
if errorlevel 1 goto failed
cd ..
".venv\Scripts\python.exe" -m backend
if errorlevel 1 goto failed
exit /b 0
:missing_setup
echo Run SETUP_APP.cmd first, then open START_APP.cmd again.
pause
exit /b 1
:failed
echo The app could not start. Check the message above. If a Python package is missing, run SETUP_APP.cmd.
pause
exit /b 1
