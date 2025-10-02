#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="${PROJECT_ROOT}/venv"

if [[ ! -d "$VENV_PATH" ]]; then
  echo "Virtualenv not found at ${VENV_PATH}. Create it with 'python3 -m venv venv'." >&2
  exit 1
fi

source "${VENV_PATH}/bin/activate"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

if [[ $# -gt 0 ]]; then
  CMD=("$@")
else
  CMD=("runserver" "${HOST}:${PORT}")
fi

python3 <<'PY'
import os, sys
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent
load_dotenv(project_root / ".env")

# Reconstruct manage.py invocation
os.chdir(project_root)
cmd = ["python3", "manage.py", *os.environ.get("DJANGO_EXTRA_ARGS", "").split(), *sys.argv[1:]]
os.execvp(cmd[0], cmd)
PY \
"${CMD[@]}"
