# syntax=docker/dockerfile:1.3

FROM python:3.11.1-slim-bullseye@sha256:fddb148df38cb61453b0ab19157f4a5ddea1b9bf0b4b1450e6126bb48d762f5b

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
