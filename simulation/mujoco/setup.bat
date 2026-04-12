@echo off
REM === SumoBot MuJoCo - Setup venv + dependencies ===
REM Run this once after cloning the repo.

cd /d "%~dp0"

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

echo Installing dependencies...
call venv\Scripts\activate.bat
pip install -r requirements.txt

echo.
echo Setup complete! You can now run:
echo   run_headless.bat          - Batch simulation
echo   run_viewer.bat            - 3D viewer
echo   run_montecarlo.bat        - Monte Carlo optimization
