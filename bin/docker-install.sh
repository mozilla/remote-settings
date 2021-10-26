#!/usr/bin/env bash
set -eo pipefail

# This file exists to make the Dockerfile easier to read.

# System packages
apt-get update
apt-get install -y --no-install-recommends \
    git \
    g++ \
    gcc \
    curl \
    mime-support \
    libpcre3-dev \
    libffi-dev \
    libpq-dev \
    libsasl2-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    libz-dev


# Get rustup https://rustup.rs/
# minimal profile https://rust-lang.github.io/rustup/concepts/profiles.html
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- --profile minimal -y
# Add cargo to PATH
source ~/.cargo/env


# Python packages
pip install --upgrade pip
pip install --no-cache-dir -r requirements.txt
uwsgi --build-plugin https://github.com/Datadog/uwsgi-dogstatsd
# The above command puts the `dogstatsd_plugin.so` in the root.
# Move it so it becomes available in the WORKDIR.
mv /dogstatsd_plugin.so /app/


# Cleanup
apt-get autoremove -y
apt-get clean
rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
