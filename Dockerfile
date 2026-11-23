FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/tmp \
    TORCH_HOME=/app/data/cache/torch

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m venv .venv \
    && .venv/bin/pip install --index-url https://download.pytorch.org/whl/cpu \
        torch==2.5.1+cpu torchaudio==2.5.1+cpu \
    && .venv/bin/pip install -r requirements.txt \
    && .venv/bin/pip check

COPY app app
COPY scripts scripts
COPY assets assets

ENTRYPOINT ["/app/.venv/bin/python"]
CMD ["scripts/make_podcast.py", "--preview", "--with-music"]
