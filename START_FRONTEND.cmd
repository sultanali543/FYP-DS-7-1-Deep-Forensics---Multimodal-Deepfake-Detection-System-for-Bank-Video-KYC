@echo off
setlocal
title Deep Forensics - Frontend development preview
cd /d "%~dp0frontend"
where node >nul 2>nul
if errorlevel 1 goto missing_node
where npm.cmd >nul 2>nul
if errorlevel 1 goto missing_node
if exist "node_modules\vite\bin\vite.js" goto start_app
echo Installing frontend dependencies. Internet access is required for this first step.
call npm.cmd install
if errorlevel 1 goto install_failed
:start_app
echo Starting the frontend development server. Default mode: DEMO.
echo In demo mode, results are fixed examples and do not analyze your video.
echo For trained visual and audio analysis, open START_APP.cmd in the project folder.
echo Developers can override the default mode through frontend/.env.local.
echo Keep this window open while using the frontend preview.
echo Press Ctrl+C here to stop the server.
call npm.cmd run dev -- --open
pause
exit /b
:missing_node
echo Node.js and npm were not found. Install a supported Node.js LTS release, then run this file again.
pause
exit /b 1
:install_failed
echo Dependency installation failed. Check your internet connection and run this file again.
pause
exit /b 1
