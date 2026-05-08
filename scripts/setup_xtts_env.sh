#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "setup-xtts now uses the unified Python 3.11 environment."
bash scripts/setup_env.sh
echo "Add XTTS reference voices:"
echo "  data/voices/xtts/mark.wav"
echo "  data/voices/xtts/gleb.wav"
echo "  data/voices/xtts/nika.wav"
echo "  data/voices/xtts/artem.wav"
