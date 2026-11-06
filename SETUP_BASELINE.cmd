@echo off
setlocal
title Deep Forensics - Baseline setup
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto install_packages
python -m venv .venv
if errorlevel 1 goto failed
:install_packages
echo Installing CPU-only packages in the project environment.
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --no-cache-dir -r ml\requirements-torch-cpu.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --no-cache-dir -r ml\requirements-lock.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m ml setup-assets
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m ml doctor
if errorlevel 1 goto failed
echo Setup complete. Pretrained assets are ready; training still needs labeled videos.
pause
exit /b 0
:failed
echo Setup stopped. Read the error above, correct it, and run this file again.
pause
exit /b 1
