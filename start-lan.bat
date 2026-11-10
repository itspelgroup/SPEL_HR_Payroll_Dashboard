@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python 3 is required. Install Python from https://www.python.org/downloads/windows/
    pause
    exit /b 1
  )
  set "PYTHON=python"
  set "PYTHON_ARGS="
) else (
  set "PYTHON=py"
  set "PYTHON_ARGS=-3"
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating the dashboard Python environment...
  %PYTHON% %PYTHON_ARGS% -m venv .venv
  if errorlevel 1 (
    echo Could not create the Python environment.
    pause
    exit /b 1
  )
  echo Installing dashboard dependencies...
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Dependency installation failed. Check internet access and try again.
    pause
    exit /b 1
  )
)

set "SPEL_HOST=0.0.0.0"
echo Starting the dashboard for LAN access on port configured in config.ini.
echo Sample mode is used unless a private config.ini enables live data.
echo Default address: http://SERVER-IP:5000
echo Press Ctrl+C to stop the server.
".venv\Scripts\python.exe" serve.py
if errorlevel 1 (
  echo The dashboard stopped with an error.
  pause
  exit /b 1
)
