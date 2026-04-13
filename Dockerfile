FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SHUNT_REACTOR_OUTPUT_DIR=/app/output \
    SHUNT_REACTOR_RUNTIME_DIR=/app/output/runtime

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        fonts-noto-cjk \
        texlive-xetex \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash appuser \
    && mkdir -p /app/output \
    && chown -R appuser:appuser /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY data ./data

RUN pip install --upgrade pip setuptools wheel \
    && pip install . \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["shunt-reactor-web"]
