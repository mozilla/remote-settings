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
    pushd mail
    rm -fr *.eml
    python mailfileserver.py --bind 0.0.0.0 9999 &
    popd

    kinto start --ini $KINTO_INI
    ;;
  uwsgistart)
    pushd mail
    rm -fr *.eml
    python mailfileserver.py --bind 0.0.0.0 9999 &
    popd

    KINTO_INI=$KINTO_INI uwsgi --http :8888 --ini $KINTO_INI
    ;;
  *)
    exec "$@"
    ;;
esac
