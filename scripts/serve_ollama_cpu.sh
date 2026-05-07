#!/usr/bin/env bash
set -euo pipefail

export CUDA_VISIBLE_DEVICES=""
export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"

exec ollama serve
