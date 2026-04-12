@echo off
REM === SumoBot MuJoCo - 3D Viewer ===
REM Usage:
REM   run_viewer.bat                  (basic enemy, vitesse normale)
REM   run_viewer.bat --smart          (smart enemy)
REM   run_viewer.bat --speed 0.5      (ralenti)

cd /d "%~dp0"
call venv\Scripts\activate.bat
python runners\viewer.py %*
