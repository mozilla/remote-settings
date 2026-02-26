FROM python:3.14.0-slim-bookworm

ENV VIRTUAL_ENV=/opt/.venv \
    PATH="/opt/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app" \
    UV_CACHE_DIR=/tmp/uv-cache

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./

RUN apt-get update && apt-get install -y --no-install-recommends wget build-essential \
 && uv venv "$VIRTUAL_ENV" \
 && uv sync --frozen --no-install-project --no-editable \
 && uv run playwright install-deps firefox \
 && uv run playwright install firefox \
 && rm -rf /var/lib/apt/lists/*

RUN addgroup --gid 10001 app \
 && adduser --disabled-password --gecos '' --gid 10001 --home /app --uid 10001 app
USER app
COPY . .
ENTRYPOINT ["./run.sh"]
