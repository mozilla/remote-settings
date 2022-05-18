# syntax=docker/dockerfile:1.3

FROM python:3.10.4-slim-bullseye@sha256:6969a4db2035769fed7f063e37bfbe16ed221ac66f9341702776940eae480e7c

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
