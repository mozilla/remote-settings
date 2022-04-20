# syntax=docker/dockerfile:1.3

FROM python:3.10.4-slim-bullseye@sha256:f5586131a316c3857cac0e2bfd8e3c19a08f1c0efa9dc8ebfcbe4d726e224ce0

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app:$PYTHONPATH"

USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends wget

RUN pip install --upgrade pip setuptools wheel
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT ["/bin/bash", "/app/run.sh"]
