# syntax=docker/dockerfile:1.3

FROM python:3.10.5-slim-bullseye@sha256:ca78039cbd3772addb9179953bbf8fe71b50d4824b192e901d312720f5902b22 as compile

RUN apt-get update && apt-get install -y --no-install-recommends \
    # Needed to download Rust
    curl \
    # Needed to build psycopg and uWSGI
    build-essential \
    libpq-dev \
    # Needed to build uwsgi-dogstatsd plugin
    git

# Get rustup https://rustup.rs/ for canonicaljson-rs
# minimal profile https://rust-lang.github.io/rustup/concepts/profiles.html
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- --profile minimal -y
# Add cargo to PATH
ENV PATH="/root/.cargo/bin:$PATH"

ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN python -m pip install --upgrade pip

COPY requirements.txt .

# Python packages
RUN python -m pip install --no-cache-dir -r requirements.txt
RUN uwsgi --build-plugin https://github.com/Datadog/uwsgi-dogstatsd


FROM python:3.10.5-slim-bullseye@sha256:ca78039cbd3772addb9179953bbf8fe71b50d4824b192e901d312720f5902b22 as server

RUN apt-get update && apt-get install -y --no-install-recommends \
    # Needed for UWSGI 
    libxml2-dev \
    # Needed for psycopg2
    libpq-dev

WORKDIR /app

ENV VIRTUAL_ENV=/opt/venv

COPY --from=compile $VIRTUAL_ENV $VIRTUAL_ENV
COPY --from=compile /dogstatsd_plugin.so .

ENV PYTHONUNBUFFERED=1 \
    PORT=8888 \
    KINTO_INI=config/local.ini \
    PATH="$VIRTUAL_ENV/bin:$PATH"

# add a non-privileged user for installing and running
# the application
RUN chown 10001:10001 /app && \
    groupadd --gid 10001 app && \
    useradd --no-create-home --uid 10001 --gid 10001 --home-dir /app app

COPY . .
RUN python -m pip install ./kinto-remote-settings

# Generate local key pair to simplify running without Autograph out of the box (see `config/testing.ini`)
RUN python -m kinto_remote_settings.signer.generate_keypair /app/ecdsa.private.pem /app/ecdsa.public.pem

# Drop down to unprivileged user
RUN chown -R 10001:10001 /app

USER 10001

EXPOSE $PORT

# Run uwsgi by default
ENTRYPOINT ["/bin/bash", "/app/bin/run.sh"]
CMD uwsgi --http :${PORT} --ini ${KINTO_INI}
