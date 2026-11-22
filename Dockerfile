# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

ARG INSTALL_EXTRAS=""

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

# Install DejaVu fonts for Polish diacritics in fpdf2 PDF export + curl for healthcheck
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast, reproducible dependency installation from uv.lock
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

# Copy dependency manifests first for better Docker layer caching
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --no-dev ${INSTALL_EXTRAS}

# Copy application source, configuration, data, and migrations
COPY src/ ./src/
COPY config/ ./config/
COPY data/ ./data/
COPY models/ ./models/
COPY scripts/ ./scripts/
COPY alembic.ini ./
COPY migrations/ ./migrations/

# Install the local package into the venv and pre-build the RAG knowledge base index
RUN uv sync --no-dev ${INSTALL_EXTRAS} \
    && .venv/bin/python -m scripts.build_knowledge_base

# Create non-root user and ensure runtime/output directories are writable
RUN useradd --create-home --shell /bin/bash kompas \
    && mkdir -p /app/data/runtime /app/data/output/archive \
    && chown -R kompas:kompas /app

USER kompas

ENV KOMPAS_ENV=dev \
    KOMPAS__SERVER__HOST=0.0.0.0 \
    KOMPAS__SERVER__PORT=8000 \
    KOMPAS__LLM__PROFILE=extractive \
    KOMPAS__EMBEDDINGS__PROFILE=hashing \
    KOMPAS__RETRIEVER__PROVIDER=bm25

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/v1/health || exit 1

CMD ["python", "-m", "kompas"]
