# syntax=docker/dockerfile:1.3

FROM python:3.10.5-slim-bullseye@sha256:ca78039cbd3772addb9179953bbf8fe71b50d4824b192e901d312720f5902b22

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
