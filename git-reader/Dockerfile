ARG UID=10001
ARG GID=10001

FROM python:3.14.0-slim-trixie

ARG UID
ARG GID

RUN apt-get update && apt-get -y install git git-lfs rsync util-linux media-types build-essential

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

RUN chown ${UID}:${GID} /app
RUN groupadd --gid ${GID} app
RUN useradd --no-create-home --uid ${UID} --gid ${GID} --home-dir /app app

RUN mkdir /app/.ssh && \
    ssh-keyscan github.com >> /app/.ssh/known_hosts && \
    chown -R app:app /app/.ssh

COPY --chown=app:app pyproject.toml uv.lock ./
COPY --chown=app:app version.json .

RUN uv sync --frozen --no-install-project

COPY --chown=app:app run.sh .
RUN chmod +x run.sh
COPY --chown=app:app app.py mimetypes.txt ./

USER app

ENV GIT_REPO_PATH=/mnt/data/latest \
    SELF_CONTAINED=false \
    GRANIAN_HOST="0.0.0.0" \
    GRANIAN_PORT=8000 \
    GRANIAN_TRUSTED_HOSTS="*" \
    PATH="/app/.venv/bin:$PATH"

EXPOSE $GRANIAN_PORT

ENTRYPOINT [ "/app/run.sh" ]
CMD [ "web" ]
