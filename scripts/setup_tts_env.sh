#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required for the isolated Silero TTS environment."
  echo "Install it first: https://docs.astral.sh/uv/"
  exit 1
fi

uv python install 3.12
uv venv .venv-tts --python 3.12
uv pip install --python .venv-tts/bin/python -r requirements.txt
uv pip install --python .venv-tts/bin/python torch --index-url https://download.pytorch.org/whl/cpu

echo "Silero TTS environment is ready: .venv-tts"
echo "Run: .venv-tts/bin/python scripts/make_tts_sample.py"
