#!/usr/bin/env bash
set -eo pipefail

: "${SERVER:=http://web:8888/v1}"

usage() {
    echo "usage: ./run.sh smoke|integration"
    echo ""
    echo "    smoke                   Start smoke tests"
    echo "    integration             Start integration tests"
    echo ""
    exit 1
}

[ $# -lt 1 ] && usage

case $1 in
smoke)
    wget -q --tries=180 --retry-connrefused --waitretry=1 -O /dev/null $SERVER || (echo "Can't reach $SERVER" && exit 1)
    http --check-status $SERVER/__heartbeat__
    http POST "$SERVER/__flush__"
    SERVER=$SERVER ./smoke-test.sh
    ;;
integration)
    echo "Integration test..."
    wget -q --tries=180 --retry-connrefused --waitretry=1 -O /dev/null $SERVER || (echo "Can't reach $SERVER" && exit 1)
    http --check-status $SERVER/__heartbeat__
    http POST "$SERVER/__flush__"
    # pytest integration_test.py
    ;;
*)
    exec "$@"
    ;;
esac
