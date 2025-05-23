FROM python:3.13.2 AS build

ENV PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    POETRY_HOME="/opt/poetry" \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    VIRTUAL_ENV=/opt/.venv \
    PATH="/opt/.venv/bin:$PATH" \
    PYTHONPATH="/app:$PYTHONPATH"

# Install Poetry
RUN python -m venv $POETRY_HOME && \
    $POETRY_HOME/bin/pip install poetry==2.0.1 && \
    $POETRY_HOME/bin/poetry --version

WORKDIR /opt
COPY pyproject.toml poetry.lock ./
RUN $POETRY_HOME/bin/poetry install --no-root


FROM python:3.13.2

ENV PATH="/opt/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/.venv \
    PYTHONPATH="/app:$PYTHONPATH"

COPY --from=build $VIRTUAL_ENV $VIRTUAL_ENV

WORKDIR /app
ADD src ./

ENTRYPOINT ["/app/main.py"]
CMD ["help"]
