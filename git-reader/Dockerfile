FROM python:3.13.2-slim-bullseye

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

RUN apt-get update && apt-get -y install git git-lfs rsync util-linux

WORKDIR /app

RUN chown 10001:10001 /app && \
    groupadd --gid 10001 app && \
    useradd --no-create-home --uid 10001 --gid 10001 --home-dir /app app

RUN mkdir /app/.ssh && \
    ssh-keyscan github.com >> /app/.ssh/known_hosts && \
    chown -R app:app /app/.ssh

COPY --chown=app:app pyproject.toml .
COPY --chown=app:app uv.lock .

RUN uv sync --locked --no-cache

COPY --chown=app:app run.sh .
RUN chmod +x run.sh
COPY --chown=app:app main.py .

USER app

ENV GIT_REPO_PATH=/mnt/data/latest
ENV SELF_CONTAINED=false

EXPOSE 8000

ENTRYPOINT [ "/app/run.sh" ]
CMD [ "web" ]
