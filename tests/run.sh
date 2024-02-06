#!/usr/bin/env bash
set -eo pipefail

: "${SERVER:=http://localhost:8888/v1}"

usage() {
    echo "usage: ./run.sh integration-test|browser-test"
    echo ""
    echo "    integration-test        Start integration tests"
    echo "    browser-test            Start browser tests"
    echo ""
    exit 1
}

[ $# -lt 1 ] && usage

wait_for_server () {
  echo "Waiting for $SERVER to become available"
  wget -q --retry-connrefused --waitretry=1 -O /dev/null $SERVER || (echo "Can't reach $SERVER" && exit 1)
  echo "verifying $SERVER heartbeat"
  http --check-status --body --json --pretty format GET $SERVER/__heartbeat__ ; echo
}

case $1 in
integration-test)
    shift
    wait_for_server
    pytest integration $@
    ;;
browser-test)
    shift
    wait_for_server
    # pytest --base-url $SERVER --verify-base-url browser_test.py --server $SERVER --log-level=DEBUG
    py.test browser_test.py --log-level=DEBUG
    ;;
*)
    exec "$@"
    ;;
esac
