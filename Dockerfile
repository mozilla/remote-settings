# syntax=docker/dockerfile:1.3

FROM python:3.9-slim-bullseye@sha256:daf74cd7c4a6d420c2979b1fc74a3000489b69a330cbc15d0ab7b4721697945a as compile

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


FROM python:3.9-slim-bullseye@sha256:daf74cd7c4a6d420c2979b1fc74a3000489b69a330cbc15d0ab7b4721697945a AS build

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
    KINTO_INI=config/example.ini \
    PATH="/opt/venv/bin:$PATH"

# add a non-privileged user for installing and running
# the application
RUN chown 10001:10001 /app && \
    groupadd --gid 10001 app && \
    useradd --no-create-home --uid 10001 --gid 10001 --home-dir /app app

COPY . .
RUN pip install ./kinto-remote-settings

# Generate local key pair to simplify running without Autograph out of the box (see `config/testing.ini`)
RUN python -m kinto_remote_settings.signer.generate_keypair /app/ecdsa.private.pem /app/ecdsa.public.pem

# Drop down to unprivileged user
RUN chown -R 10001:10001 /app

USER 10001

EXPOSE $PORT

# Run uwsgi by default
ENTRYPOINT ["/bin/bash", "/app/bin/run.sh"]
CMD uwsgi --ini ${KINTO_INI}
