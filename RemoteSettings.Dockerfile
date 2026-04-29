############################
# Compile stage
############################

FROM python:3.14.3 AS compile

ENV VIRTUAL_ENV=/opt/.venv \
    PATH="/opt/.venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /opt
COPY ./uv.lock ./pyproject.toml ./
COPY ./kinto-slack ./kinto-slack
RUN uv venv $VIRTUAL_ENV
RUN uv sync --frozen --no-install-project --no-editable \
    --no-group kinto-remote-settings \
    --no-group cronjobs \
    --no-group git-reader \
    --no-group dev \
    --no-group docs

COPY ./kinto-remote-settings ./kinto-remote-settings
RUN uv sync --frozen --no-install-project --no-editable \
    --group kinto-remote-settings \
    --no-group cronjobs \
    --no-group git-reader \
    --no-group dev \
    --no-group docs


############################
# Kinto Admin stage
############################

# We pull the Kinto Admin assets at the version specified in `kinto-admin/VERSION`.
FROM alpine:3 AS get-admin
WORKDIR /opt
COPY bin/pull-kinto-admin.sh .
COPY kinto-admin/ kinto-admin/
RUN ./pull-kinto-admin.sh


############################
# Production stage
############################

FROM python:3.14.3-slim AS production

ENV KINTO_INI=config/local.ini \
    KINTO_ADMIN_ASSETS_PATH=/app/kinto-admin/build/ \
    PATH="/opt/.venv/bin:$PATH" \
    GRANIAN_HOST="0.0.0.0" \
    GRANIAN_PORT=8888 \
    GRANIAN_TRUSTED_HOSTS="*" \
    GRANIAN_METRICS_ENABLED=true \
    GRANIAN_METRICS_ADDRESS="0.0.0.0" \
    GRANIAN_METRICS_PORT=9090 \
    # cap concurrent WSGI requests to something reasonable relative to the DB pool size
    GRANIAN_BACKPRESSURE="32" \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/.venv \
    PROMETHEUS_MULTIPROC_DIR="/tmp/metrics" \
    VERSION_FILE=/app/version.json

COPY /bin/update_and_install_system_packages.sh /opt
RUN /opt/update_and_install_system_packages.sh \
    # Needed for psycopg2
    libpq-dev

COPY --from=compile $VIRTUAL_ENV $VIRTUAL_ENV

WORKDIR /app
RUN chown 10001:10001 /app && \
    groupadd --gid 10001 app && \
    useradd --no-create-home --uid 10001 --gid 10001 --home-dir /app app
COPY --chown=app:app . .

COPY --from=get-admin /opt/kinto-admin/build $KINTO_ADMIN_ASSETS_PATH

# Generate local key pair to simplify running without Autograph out of the box (see `config/testing.ini`)
RUN python -m kinto_remote_settings.signer.generate_keypair /app/ecdsa.private.pem /app/ecdsa.public.pem

EXPOSE $GRANIAN_PORT $GRANIAN_METRICS_PORT
USER app
ENTRYPOINT ["./bin/run.sh"]
# Run server by default
CMD ["start"]


############################
# Local stage
############################

FROM production AS local

# Serve attachments at /attachments
ENV GRANIAN_STATIC_PATH_ROUTE=/attachments
ENV GRANIAN_STATIC_PATH_MOUNT=/tmp/attachments

# create directories for volume mounts used in browser tests / local development
RUN mkdir -p -m 777 /app/mail && mkdir -p -m 777 /app/slack && mkdir -p -m 777 /tmp/attachments
