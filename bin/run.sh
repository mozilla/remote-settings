#!/usr/bin/env bash
set -eo pipefail

usage() {
  echo "usage: ./bin/run.sh migrate|start|uwsgistart|bash|whatevercommandyouwant"
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
    uwsgi --http :$PORT --ini $KINTO_INI
    ;;
  *)
    exec "$@"
    ;;
esac
