FROM python:3.8.5-slim@sha256:d2cbcf4d205ca2210e46915f79f486dffe710d2b1deedbe4f7c017e2f9d9b6a8

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
