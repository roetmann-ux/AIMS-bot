#!/bin/bash
# AIMS — double-click this file to launch. It opens http://localhost:8765 in your browser.
# Leave the Terminal window that appears OPEN while you use the app; close it to stop.
cd "$(dirname "$0")" || exit 1
PORT=8765

if [ ! -x ".venv/bin/uvicorn" ]; then
  echo "First-time setup — building the environment (this takes 1–2 minutes)…"
  python3 -m venv .venv || { echo; echo "Python 3 is required. Install it from python.org, then double-click this again."; read -r -p "Press Return to close."; exit 1; }
  ./.venv/bin/python -m pip install --quiet --upgrade pip
  ./.venv/bin/python -m pip install --quiet -r requirements.txt || { echo "Install failed — see messages above."; read -r -p "Press Return to close."; exit 1; }
fi

echo
echo "  AIMS is starting…  opening http://localhost:$PORT"
echo "  (keep this window open; close it to stop the app)"
echo
( sleep 2; open "http://localhost:$PORT" ) &
exec ./.venv/bin/uvicorn app:app --port "$PORT"
