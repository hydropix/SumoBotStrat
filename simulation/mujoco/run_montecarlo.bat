@echo off
REM === SumoBot MuJoCo - Monte Carlo Optimization ===
REM Usage:
REM   run_montecarlo.bat                                       (40 configs, basic)
REM   run_montecarlo.bat --smart                               (smart enemy)
REM   run_montecarlo.bat --configs 80 --rounds 200 --smart     (full optimization)
REM   run_montecarlo.bat --output results.json                 (save to file)

cd /d "%~dp0"
call venv\Scripts\activate.bat
python runners\montecarlo.py %*
