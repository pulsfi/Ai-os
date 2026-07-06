@echo off
REM ============================================================
REM  OS AI backend — 24/7 auto-restarting launcher
REM  Double-click this, or register it as a scheduled task.
REM  If the backend ever crashes, it waits 5s and restarts.
REM  The bots trade inside this process — keep it running.
REM ============================================================
title OS AI Backend (24/7)
cd /d "%~dp0"

:loop
echo [%date% %time%] starting OS AI backend on http://127.0.0.1:8000 ...
".venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8000
echo [%date% %time%] backend stopped (exit %errorlevel%). Restarting in 5s...
timeout /t 5 /nobreak >nul
goto loop
