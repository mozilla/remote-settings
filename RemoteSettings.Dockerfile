FROM python:3.11.1 as compile

ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /opt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    uwsgi --build-plugin https://github.com/Datadog/uwsgi-dogstatsd

FROM python:3.11.1-slim as server

ENV KINTO_INI=config/local.ini \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8888 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv

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
RUN pip install --no-cache-dir ./kinto-remote-settings

# Generate local key pair to simplify running without Autograph out of the box (see `config/testing.ini`)
RUN python -m kinto_remote_settings.signer.generate_keypair /app/ecdsa.private.pem /app/ecdsa.public.pem

EXPOSE $PORT
USER app
# Run uwsgi by default
ENTRYPOINT ["/bin/bash", "/app/bin/run.sh"]
CMD ["sh", "-c", "uwsgi --http :${PORT} --ini ${KINTO_INI}"]