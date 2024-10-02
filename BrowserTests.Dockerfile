FROM python:3.12.7 as build

ENV PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    POETRY_HOME="/opt/poetry" \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    VIRTUAL_ENV=/opt/.venv \
    PATH="/opt/.venv/bin:$PATH"

# Install Poetry
RUN python -m venv $POETRY_HOME && \
    $POETRY_HOME/bin/pip install poetry==1.4.1 && \
    $POETRY_HOME/bin/poetry --version

WORKDIR /opt
COPY pyproject.toml poetry.lock ./
RUN $POETRY_HOME/bin/poetry install --only browser-tests --no-root

FROM python:3.12.7

ENV PATH="/opt/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/.venv \
    PYTHONPATH="/app:$PYTHONPATH"

COPY /bin/update_and_install_system_packages.sh /opt
RUN /opt/update_and_install_system_packages.sh wget

COPY --from=build $VIRTUAL_ENV $VIRTUAL_ENV

RUN playwright install --with-deps firefox

WORKDIR /app
COPY tests/ pyproject.toml ./
# ./tests/run.sh, not ./bin/run.sh
ENTRYPOINT ["/app/run.sh"]
