@echo off
rem Meme Scalper (PAPER MODE) - runs continuously until this window is closed.
title AI-OS Meme Scalper (paper)
cd /d "%~dp0"
node scalper.mjs --loop
pause
