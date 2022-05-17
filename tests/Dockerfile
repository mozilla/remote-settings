# syntax=docker/dockerfile:1.3

FROM python:3.10.4-slim-bullseye@sha256:b01a8dcfa22e9dbc960e7c0855ff79bf1b334bd14efec47d91e5dfa67c697e6a

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
