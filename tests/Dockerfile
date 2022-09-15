# syntax=docker/dockerfile:1.3

FROM python:3.10.7-slim-bullseye@sha256:90b7cdff7f8bdbf43778bd5131bb62f7c83495462f562bd62baefdb69bf09bca

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app:$PYTHONPATH"

USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends wget curl build-essential

# Remove Rust installation when https://github.com/mozilla-services/python-canonicaljson-rs/issues/3 is fixed.
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- --profile minimal -y
ENV PATH="/root/.cargo/bin:$PATH"

RUN python -m pip install --upgrade pip
COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT ["/bin/bash", "/app/run.sh"]
