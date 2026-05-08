#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required for the unified project environment."
  echo "Install it first: https://docs.astral.sh/uv/"
  exit 1
fi

uv python install 3.11
uv venv .venv --python 3.11 --clear
uv pip install --python .venv/bin/python -r requirements.txt
uv pip install --python .venv/bin/python torch==2.5.1+cpu torchaudio==2.5.1+cpu --index-url https://download.pytorch.org/whl/cpu
uv pip install --python .venv/bin/python "TTS>=0.22,<0.23"
uv pip install --python .venv/bin/python "transformers==4.33.3"

mkdir -p data/voices/xtts

echo "Unified environment is ready: .venv"
echo "Python: $(.venv/bin/python --version)"
echo "Run tests: make test"
