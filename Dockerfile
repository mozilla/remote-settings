# syntax=docker/dockerfile:1.3

FROM python:3.10.2-slim-bullseye@sha256:ca2a31f21938f24bab02344bf846a90cc2bff5bd0e5a53b24b5dfcb4519ea8a3 as compile

RUN apt-get update && apt-get install -y --no-install-recommends \
    # Needed to download Rust
    curl \
    # Needed to build psycopg and uWSGI 
    build-essential \
    python-dev \
    libpq-dev \
    # Needed to build uwsgi-dogstatsd plugin
    git

# Get rustup https://rustup.rs/ for canonicaljson-rs
# minimal profile https://rust-lang.github.io/rustup/concepts/profiles.html
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- --profile minimal -y
# Add cargo to PATH
ENV PATH="/root/.cargo/bin:$PATH"

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --upgrade pip

COPY requirements.txt .

# Python packages
RUN pip install --no-cache-dir -r requirements.txt
RUN uwsgi --build-plugin https://github.com/Datadog/uwsgi-dogstatsd


FROM python:3.10.2-slim-bullseye@sha256:ca2a31f21938f24bab02344bf846a90cc2bff5bd0e5a53b24b5dfcb4519ea8a3 AS build

RUN apt-get update && apt-get install -y --no-install-recommends \
    # Needed for UWSGI 
    libxml2-dev \
    # Needed for psycopg2
    libpq-dev

WORKDIR /app

COPY --from=compile /opt/venv /opt/venv
COPY --from=compile /dogstatsd_plugin.so .

ENV PYTHONUNBUFFERED=1 \
    PORT=8888 \
    PATH="/opt/venv/bin:$PATH"

# add a non-privileged user for installing and running
# the application
RUN chown 10001:10001 /app && \
    groupadd --gid 10001 app && \
    useradd --no-create-home --uid 10001 --gid 10001 --home-dir /app app

COPY . .
RUN pip install ./kinto-remote-settings

# Drop down to unprivileged user
RUN chown -R 10001:10001 /app

USER 10001

EXPOSE $PORT

# Run uwsgi by default
ENTRYPOINT ["/bin/bash", "/app/bin/run.sh"]
CMD ["uwsgi", "--ini", "/etc/kinto.ini"]
