#!/usr/bin/env bash
set -eo pipefail

: "${KINTO_INI:=config/example.ini}"

usage() {
  echo "usage: ./bin/run.sh uwsgistart|start|bash|whatevercommandyouwant"
  exit 1
}

[ $# -lt 1 ] && usage

case $1 in
  migrate)
    kinto migrate --ini $KINTO_INI
    ;;
  start)
    kinto start --ini $KINTO_INI
    ;;
  uwsgistart)
    KINTO_INI=$KINTO_INI uwsgi --http :8888 --ini $KINTO_INI
    ;;
  *)
    exec "$@"
    ;;
esac
