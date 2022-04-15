# syntax=docker/dockerfile:1.3

FROM python:3.10.4-slim-bullseye@sha256:80ebadfc9b83cf037ebe9a7db0631101b7c18c58f4197de0ef2badb268a35a45

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
