@echo off
rem Start the development server with auto-reload.
cd /d "%~dp0.."
call .venv\Scripts\activate
uvicorn main:app --reload --port 8000
