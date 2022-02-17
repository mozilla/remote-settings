# syntax=docker/dockerfile:1.3

FROM python:3.9-slim-bullseye@sha256:daf74cd7c4a6d420c2979b1fc74a3000489b69a330cbc15d0ab7b4721697945a AS tests

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
