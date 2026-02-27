FROM python:3.14.0 AS build

ENV VIRTUAL_ENV=/opt/.venv \
    PATH="/opt/.venv/bin:$PATH" \
    PYTHONPATH="/app:$PYTHONPATH"

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /opt
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project


FROM python:3.14.0-slim

ENV PATH="/opt/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/.venv \
    PYTHONPATH="/app:$PYTHONPATH"

COPY --from=build $VIRTUAL_ENV $VIRTUAL_ENV

WORKDIR /app
ADD src ./

RUN chown 10001:10001 /app && \
    groupadd --gid 10001 app && \
    useradd --no-create-home --uid 10001 --gid 10001 --home-dir /app app

USER app

ENTRYPOINT ["/app/main.py"]
CMD ["help"]
