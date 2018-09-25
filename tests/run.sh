#!/usr/bin/env bash
set -eo pipefail

: "${SERVER:=http://web:8888/v1}"
: "${MAILFILESERVER:=http://web:9999}"

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
    wget -q --tries=10 --retry-connrefused --waitretry=1 -O /dev/null $SERVER || (echo "Can't reach $SERVER" && exit 1)
    http --check-status $SERVER/__heartbeat__
    # http --check-status $SERVER/__api__
    http POST "$SERVER/__flush__"
    SERVER=$SERVER MAILFILESERVER=$MAILFILESERVER ./smoke-test.sh
    ;;
  *)
    exec "$@"
    ;;
esac
