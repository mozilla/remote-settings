#!/usr/bin/env bash
set -eo pipefail

: "${SERVER:=http://localhost:8888/v1}"

usage() {
    echo "usage: ./run.sh start"
    echo ""
    echo "    start                         Start tests"
    echo ""
    exit 1
}

[ $# -lt 1 ] && usage

case $1 in
start)
    shift
    wget -q --tries=180 --retry-connrefused --waitretry=1 -O /dev/null $SERVER || (echo "Can't reach $SERVER" && exit 1)
    http -q --check-status $SERVER/__heartbeat__
    pytest integration_test.py $@
    pytest --driver Remote --capability browserName firefox --base-url $SERVER/admin --verify-base-url browser_test.py --server $SERVER
    ;;
*)
    exec "$@"
    ;;
esac
