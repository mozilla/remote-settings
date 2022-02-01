#!/usr/bin/env bash
set -eo pipefail

: "${SERVER:=http://web:8888/v1}"

usage() {
    echo "usage: ./run.sh tests"
    echo ""
    echo "    tests                         Start tests"
    echo ""
    exit 1
}

[ $# -lt 1 ] && usage

case $1 in
tests)
    wget -q --tries=180 --retry-connrefused --waitretry=1 -O /dev/null $SERVER || (echo "Can't reach $SERVER" && exit 1)
    http -q --check-status $SERVER/__heartbeat__
    pytest integration_test.py --server $SERVER
    pytest --driver Remote --capability browserName firefox --base-url $SERVER/admin --verify-base-url browser_test.py --server $SERVER
    ;;
*)
    exec "$@"
    ;;
esac
