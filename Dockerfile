FROM python:3.14-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.9.13 /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock .python-version /app/
RUN uv sync --frozen --no-dev

COPY server /app/server
COPY ingest /app/ingest
COPY migrations /app/migrations
COPY tests/fixtures /app/tests/fixtures

EXPOSE 8000
CMD ["uv", "run", "--no-dev", "python", "-m", "server.main"]
