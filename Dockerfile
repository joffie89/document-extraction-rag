FROM node:24-alpine AS web-build

WORKDIR /build
COPY apps/web/package.json ./
RUN npm install --no-audit --no-fund
COPY apps/web/ ./
RUN npm run build


FROM python:3.12-slim-bookworm AS python-build

COPY --from=ghcr.io/astral-sh/uv:0.5.29 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY apps/backend/src/ ./apps/backend/src/
RUN uv sync --frozen --no-dev --no-editable


FROM python-build AS python-build-full

RUN uv sync --frozen --no-dev --no-editable --extra full


FROM python:3.12-slim-bookworm AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/apps/backend/src" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 appuser \
    && mkdir --parents /app/data \
    && chown --recursive appuser:appuser /app

WORKDIR /app
COPY --from=python-build --chown=appuser:appuser /app/.venv ./.venv
COPY --chown=appuser:appuser apps/backend/src/ ./apps/backend/src/
COPY --chown=appuser:appuser apps/backend/migrations/ ./apps/backend/migrations/
COPY --chown=appuser:appuser alembic.ini ./
COPY --from=web-build --chown=appuser:appuser /build/dist ./apps/web/dist

USER appuser
EXPOSE 8000
STOPSIGNAL SIGTERM

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4)"

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn document_rag.main:app --host 0.0.0.0 --port 8000 --workers 1"]


FROM runtime AS full-runtime

USER root
COPY --from=python-build-full --chown=appuser:appuser /app/.venv /app/.venv
RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        ffmpeg \
        libreoffice-calc \
        libreoffice-impress \
        libreoffice-writer \
    && rm -rf /var/lib/apt/lists/*
USER appuser


FROM runtime AS final
