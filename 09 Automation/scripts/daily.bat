@echo off
rem Run one daily training cycle (snapshot live chain -> learn -> update vault).
cd /d "%~dp0"
node daily-cycle.mjs
