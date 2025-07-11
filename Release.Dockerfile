ARG BASE_IMG=mozilla/remote-settings:latest
FROM ${BASE_IMG}

WORKDIR /app
COPY version.json .
