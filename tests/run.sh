#!/usr/bin/env bash
set -eo pipefail

: "${SERVER:=http://localhost:8888/v1}"

wait_for_server () {
  echo "Waiting for $SERVER to become available"
  wget -q --retry-connrefused --waitretry=1 -O /dev/null $SERVER || (echo "Can't reach $SERVER" && exit 1)
  echo "verifying $SERVER heartbeat"
  http --check-status --body --json --pretty format GET $SERVER/__heartbeat__ ; echo
}

shift
wait_for_server
pytest --browser firefox $@
