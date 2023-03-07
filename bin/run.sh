#!/usr/bin/env bash
set -eo pipefail

usage() {
  echo "usage: ./bin/run.sh migrate|start|whatevercommandyouwant"
  exit 1
}

[ $# -lt 1 ] && usage
case $1 in
  migrate)
    kinto migrate --ini $KINTO_INI
    ;;
  start)
    uwsgi --http :$PORT --ini $KINTO_INI
    ;;
  *)
    exec "$@"
    ;;
esac
