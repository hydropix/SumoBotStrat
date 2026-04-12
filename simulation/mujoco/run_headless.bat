@echo off
REM === SumoBot MuJoCo - Headless Batch Simulation ===
REM Usage:
REM   run_headless.bat                     (200 rounds, basic enemy)
REM   run_headless.bat --rounds 500        (500 rounds)
REM   run_headless.bat --smart             (smart enemy)
REM   run_headless.bat --rounds 100 --smart --verbose

cd /d "%~dp0"
call venv\Scripts\activate.bat
python runners\headless.py %*
