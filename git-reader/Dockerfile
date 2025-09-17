FROM python:3.13.2-slim-bullseye

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

RUN chown 10001:10001 /app && \
    groupadd --gid 10001 app && \
    useradd --no-create-home --uid 10001 --gid 10001 --home-dir /app app

COPY --chown=app:app pyproject.toml .
COPY --chown=app:app uv.lock .

RUN uv sync --locked --no-cache

COPY --chown=app:app main.py .

USER app

ENV GIT_REPO_PATH=/mnt/data
ENV SELF_CONTAINED=false

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
