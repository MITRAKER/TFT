@echo off
setlocal
rem Bootstrap a Windows PC for this repository: install Python and the GitHub CLI
rem if they are missing, sign in to GitHub, and apply the repository settings.
rem Safe to run again at any time.
rem
rem   Double-click this file, or run:  tools\bootstrap_windows.cmd [OWNER/NAME]

set "REPO=%~1"
if "%REPO%"=="" set "REPO=MITRAKER/TFT"
set "PY_DIR=%LOCALAPPDATA%\Programs\Python\Python313"
set "GH_DIR=%ProgramFiles%\GitHub CLI"
set "PATH=%PY_DIR%;%PY_DIR%\Scripts;%GH_DIR%;%PATH%"

where winget >nul 2>nul
if errorlevel 1 (
  echo winget is not available on this PC.
  echo Install Python from https://www.python.org/downloads/ with "Add python.exe to PATH" ticked,
  echo and the GitHub CLI from https://cli.github.com, then run this script again.
  pause
  exit /b 1
)

python --version >nul 2>nul
if errorlevel 1 (
  echo Installing Python 3.13 ...
  winget install -e --id Python.Python.3.13 --accept-package-agreements --accept-source-agreements
)

gh --version >nul 2>nul
if errorlevel 1 (
  echo Installing the GitHub CLI ...
  winget install -e --id GitHub.cli --accept-package-agreements --accept-source-agreements
)

python --version >nul 2>nul
if errorlevel 1 (
  echo Python is still not available. Open a new Command Prompt and run this script again.
  pause
  exit /b 1
)
gh --version >nul 2>nul
if errorlevel 1 (
  echo The GitHub CLI is still not available. Open a new Command Prompt and run this script again.
  pause
  exit /b 1
)

gh auth status >nul 2>nul
if errorlevel 1 (
  echo Signing in to GitHub. Follow the instructions in the browser.
  gh auth login --web --hostname github.com --git-protocol https
)

echo Applying the repository settings to %REPO% ...
python "%~dp0configure_repository.py" --repo %REPO%
echo.
echo Done. Review the lines above. This script is safe to run again.
pause
