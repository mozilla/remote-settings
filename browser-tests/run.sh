#!/usr/bin/env bash
set -eo pipefail

: "${SERVER:=http://localhost:8888/v1}"
: "${HEARTBEAT_TIMEOUT:=120}"

deadline=$((SECONDS + HEARTBEAT_TIMEOUT))
until wget -qO- "$SERVER/__heartbeat__" >/dev/null; do
  if ((SECONDS >= deadline)); then
    echo "$SERVER/__heartbeat__ not healthy after ${HEARTBEAT_TIMEOUT}s:"
    wget -qO- --content-on-error "$SERVER/__heartbeat__" || true
    echo
    exit 1
  fi
  sleep 1
done

pytest --browser firefox --timeout=120 -v \
  --tracing=retain-on-failure --screenshot=only-on-failure "$@"
