@echo off
cd /d "%~dp0"
chcp 65001 > nul
echo Starting Jasmin AI...
.\venv\Scripts\python main.py
pause
