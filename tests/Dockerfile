# syntax=docker/dockerfile:1.3

FROM python:3.10.4-slim-bullseye@sha256:cd62775c2141dc3d06c1b284ceda8ebe329d588ab398b0fc296248bca5fec64a AS tests

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app:$PYTHONPATH"

USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends wget

RUN pip install --upgrade pip
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT ["/bin/bash", "/app/run.sh"]
