#!/bin/sh
set -eu
netinit
exec /docker-entrypoint.sh "$@"
