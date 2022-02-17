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
  wget -q --tries=180 --retry-connrefused --waitretry=1 -O /dev/null $SERVER/ || (echo "Can't reach $SERVER" && exit 1)
  http -q --check-status $SERVER/__heartbeat__
}

case $1 in
integration-test)
    shift
    wait_for_server
    pytest integration_test.py $@
    ;;
browser-test)
    shift
    wait_for_server
    pytest --driver Remote --capability browserName firefox --base-url $SERVER/admin/ --verify-base-url browser_test.py --server $SERVER
    ;;
*)
    exec "$@"
    ;;
esac
