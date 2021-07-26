FROM python:3.9.6-slim@sha256:5f8d3734d4b4016391ebc0162526b8335f2c16acc423d8424c1582c73a8bb053

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

COPY requirements.txt .
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
