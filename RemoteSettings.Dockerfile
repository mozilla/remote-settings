FROM python:3.12.1 as compile

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
COPY ./poetry.lock ./pyproject.toml ./
RUN $POETRY_HOME/bin/poetry install --only main --no-root && \
    uwsgi --build-plugin https://github.com/Datadog/uwsgi-dogstatsd

# though we have kinto-remote-settings specified as a dependency in
# pyproject.toml, we have it configured to install in editable mode for local
# development. For building the container, we only install the "main"
# dependency group so that we can use pip to install the packages in
# non-editable mode
COPY ./kinto-remote-settings ./kinto-remote-settings
COPY version.json .
RUN pip install ./kinto-remote-settings

# We build the Kinto Admin assets at the specific
# version specified in `kinto-admin/VERSION`.
FROM node:21.6.1 as build-admin
WORKDIR /opt
COPY bin/pull-kinto-admin.sh .
COPY kinto-admin/ kinto-admin/
RUN ./pull-kinto-admin.sh


FROM python:3.12.1-slim as production

ENV KINTO_INI=config/local.ini \
    KINTO_ADMIN_ASSETS_PATH=/app/kinto-admin/build/ \
    PATH="/opt/.venv/bin:$PATH" \
    PORT=8888 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/.venv

COPY /bin/update_and_install_system_packages.sh /opt
RUN /opt/update_and_install_system_packages.sh \
    # Needed for UWSGI
    libxml2-dev \
    # Needed for psycopg2
    libpq-dev

COPY --from=compile $VIRTUAL_ENV $VIRTUAL_ENV

WORKDIR /app
RUN chown 10001:10001 /app && \
    groupadd --gid 10001 app && \
    useradd --no-create-home --uid 10001 --gid 10001 --home-dir /app app
COPY --chown=app:app . .
COPY --from=compile /opt/dogstatsd_plugin.so .

COPY --from=build-admin /opt/kinto-admin/build $KINTO_ADMIN_ASSETS_PATH

# Generate local key pair to simplify running without Autograph out of the box (see `config/testing.ini`)
RUN python -m kinto_remote_settings.signer.generate_keypair /app/ecdsa.private.pem /app/ecdsa.public.pem

EXPOSE $PORT
USER app
ENTRYPOINT ["./bin/run.sh"]
# Run uwsgi by default
CMD ["start"]

FROM production as local
# create directories for volume mounts used in integration tests / local development
RUN mkdir -p -m 777 /app/mail && mkdir -p -m 777 /tmp/attachments
