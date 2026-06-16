@echo off
setlocal
cd /d "%~dp0"
set PORT=8765

if not exist ".venv\Scripts\python.exe" (
  echo First-time setup - building the environment. This takes 1-2 minutes...
  py -3 -m venv .venv 2>nul
  if not exist ".venv\Scripts\python.exe" python -m venv .venv 2>nul
  if not exist ".venv\Scripts\python.exe" (
    echo.
    echo Python 3 was not found. Install it from https://www.python.org/downloads/
    echo During install, TICK the box "Add Python to PATH". Then double-click this file again.
    echo.
    pause
    exit /b 1
  )
  ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
  ".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
)

echo.
echo   AIMS is starting...  opening http://localhost:%PORT%
echo   Keep this window open while you use the app. Close it to stop.
echo   (If the page cannot connect, wait ~5 seconds and refresh.)
echo.
start "" http://localhost:%PORT%
".venv\Scripts\python.exe" -m uvicorn app:app --port %PORT%
