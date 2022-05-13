# syntax=docker/dockerfile:1.3

FROM python:3.10.4-slim-bullseye@sha256:0bad1416b17b8e00eea0fae755c20628b3eecfc42cfb5d445952fd586a2ccb29

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
