# syntax=docker/dockerfile:1.3

FROM python:3.10.4-slim-bullseye@sha256:ee1b667a08d764018cbe68cd76413b12ac1d1588e60125dc5dc5a31fa08c1f0b

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
