FROM python:3.14.0-slim-bookworm AS build

ENV VIRTUAL_ENV=/opt/.venv \
    PATH="/opt/.venv/bin:$PATH" \
    PYTHONPATH="/app:$PYTHONPATH"

RUN apt-get update && apt-get -y install build-essential

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /opt
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

FROM python:3.14.0-slim-bookworm

ENV PATH="/opt/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/.venv \
    PYTHONPATH="/app:$PYTHONPATH"

RUN apt-get update && apt-get -y install wget build-essential

RUN addgroup --gid 10001 app && \
    adduser --disabled-password --gecos '' --gid 10001 --home /app --uid 10001 app

COPY --from=build --chown=app:app $VIRTUAL_ENV $VIRTUAL_ENV

RUN playwright install-deps firefox

USER app
RUN playwright install firefox

WORKDIR /app
COPY . .
ENTRYPOINT ["/app/run.sh"]
