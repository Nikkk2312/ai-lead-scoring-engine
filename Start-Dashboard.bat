@echo off
REM ============================================================
REM  AI Lead Scoring Engine - one-click dashboard launcher
REM  Starts the Flask server (auto-seeds sample data if empty)
REM  and opens the dashboard in your browser.
REM ============================================================
setlocal
cd /d "%~dp0"

set "PY=C:\Users\niket\AppData\Local\Programs\Python\Python311\python.exe"
if not exist "%PY%" set "PY=python"

echo Starting AI Lead Scoring dashboard...
start "Lead Scoring Dashboard" "%PY%" main.py dashboard

REM give the server a moment to bind port 5000, then open the browser
timeout /t 4 /nobreak >nul
start "" "http://localhost:5000/"

echo.
echo Dashboard running at http://localhost:5000/
echo    Login:  admin  /  changeme
echo Close the "Lead Scoring Dashboard" window to stop the server.
echo.
pause
