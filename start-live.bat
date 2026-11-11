@echo off
setlocal
cd /d "%~dp0"
set "SPEL_CONFIG_FILE=%~dp0config.ini"
set "SPEL_HOST=0.0.0.0"

if not exist "config.ini" (
  echo Missing config.ini. Configure the live SQL server settings first.
  pause
  exit /b 1
)

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

".venv\Scripts\python.exe" -c "from dashboard.config import load_settings,build_connection_string; s=load_settings(); assert s.get('application','data_mode') == 'live' and s.getboolean('database','enabled') and s.getboolean('security','enabled') and s.getboolean('deployment','live_only'), 'Set live mode, database, authentication and live_only in config.ini'; assert not s.get('database','server').strip().startswith('REPLACE_'), 'Set database.server in config.ini'; build_connection_string(s)"
if errorlevel 1 (
  echo Live configuration is incomplete. Check config.ini; no sample mode is available in this package.
  pause
  exit /b 1
)

echo Starting live dashboard on port configured in config.ini.
echo Press Ctrl+C to stop the server.
".venv\Scripts\python.exe" serve.py
if errorlevel 1 (
  echo The dashboard stopped with an error.
  pause
  exit /b 1
)
