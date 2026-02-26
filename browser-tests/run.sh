#!/usr/bin/env bash
set -eo pipefail

: "${SERVER:=http://localhost:8888/v1}"

until wget -qO- "$SERVER/__heartbeat__" >/dev/null; do
  sleep 1
done

pytest --browser firefox --timeout=120 -v \
  --tracing=retain-on-failure --screenshot=only-on-failure "$@"
