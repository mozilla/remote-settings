ARG UID=10001
ARG GID=10001

FROM python:3.14.0-slim-trixie

ARG UID
ARG GID

ENV PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    VIRTUAL_ENV=/opt/.venv \
    PATH="/opt/.venv/bin:$PATH"

RUN apt-get update && apt-get -y install git git-lfs rsync util-linux media-types build-essential

# Install Poetry
RUN python -m venv $VIRTUAL_ENV && \
    pip install poetry==2.0.1 && \
    poetry --version

WORKDIR /app

RUN chown ${UID}:${GID} /app
RUN groupadd --gid ${GID} app
RUN useradd --no-create-home --uid ${UID} --gid ${GID} --home-dir /app app

RUN mkdir /app/.ssh && \
    ssh-keyscan github.com >> /app/.ssh/known_hosts && \
    chown -R app:app /app/.ssh

COPY --chown=app:app pyproject.toml .
COPY --chown=app:app poetry.lock .

RUN poetry install --no-root

COPY --chown=app:app run.sh .
RUN chmod +x run.sh
COPY --chown=app:app app.py mimetypes.txt ./

USER app

ENV GIT_REPO_PATH=/mnt/data/latest
ENV SELF_CONTAINED=false

EXPOSE 8000

ENTRYPOINT [ "/app/run.sh" ]
CMD [ "web" ]
