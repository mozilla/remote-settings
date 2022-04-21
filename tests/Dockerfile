# syntax=docker/dockerfile:1.3

FROM python:3.10.4-slim-bullseye@sha256:ad719a882ac0594bdc92abccff22e5b6713bbf9893320264fd9e8affd8a6f470

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
