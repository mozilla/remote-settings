FROM python:3.8.3-slim@sha256:836f9dd208ce67d0b675ea1a05d1ff05c65449c0e56071cab67b9e5b03dc2557

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/ \
    PORT=8888

EXPOSE $PORT

# add a non-privileged user for installing and running
# the application
RUN mkdir /app && \
    chown 10001:10001 /app && \
    groupadd --gid 10001 app && \
    useradd --no-create-home --uid 10001 --gid 10001 --home-dir /app app

COPY requirements/default.txt .
COPY requirements/prod.txt .
COPY requirements/constraints.txt .
COPY bin/docker-install.sh .
RUN ./docker-install.sh

COPY . /app

# Switch back to home directory
WORKDIR /app

# Drop down to unprivileged user
RUN chown -R 10001:10001 /app

USER 10001


# Run uwsgi by default
ENTRYPOINT ["/bin/bash", "/app/bin/run.sh"]
CMD ["uwsgi", "--ini", "/etc/kinto.ini"]
