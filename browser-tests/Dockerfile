FROM python:3.14.0-slim-bookworm

ENV UV_PROJECT_ENVIRONMENT=/opt/.venv \
    PATH="/opt/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app" \
    UV_CACHE_DIR=/tmp/uv-cache

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /opt
COPY pyproject.toml uv.lock ./

RUN apt-get update && apt-get install -y --no-install-recommends wget build-essential \
 && uv venv "$UV_PROJECT_ENVIRONMENT" \
 && uv sync --frozen --no-install-project --no-editable \
 && playwright install-deps firefox \
 && rm -rf /var/lib/apt/lists/* /tmp/uv-cache

RUN addgroup --gid 10001 app \
 && adduser --disabled-password --gecos '' --gid 10001 --home /app --uid 10001 app
USER app
RUN playwright install firefox

WORKDIR /app
COPY . .
ENTRYPOINT ["./run.sh"]
