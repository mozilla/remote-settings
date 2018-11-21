#!/usr/bin/env bash
set -eo pipefail

# This file exists to make the Dockerfile easier to read.

# System packages
apt-get update
apt-get install -y --no-install-recommends \
    git \
    gcc \
    libffi-dev \
    libpq-dev \
    libsasl2-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev


# Python packages
pip install --no-cache-dir -r default.txt -r prod.txt -c constraints.txt
uwsgi --build-plugin https://github.com/Datadog/uwsgi-dogstatsd
# The above command puts the `dogstatsd_plugin.so` in the root.
# Move it so it becomes available in the WORKDIR.
mv /dogstatsd_plugin.so /app/


# Cleanup
apt-get autoremove -y
apt-get clean
rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
