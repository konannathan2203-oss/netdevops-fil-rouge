#!/bin/sh
# Poste client : applique ses routes puis reste en attente.
# Avec ONESHOT=1, applique les routes et s'arrete (utilise comme
# "sidecar" pour router le blackbox exporter via router-fw).
set -eu
netinit

if [ "${ONESHOT:-0}" = "1" ]; then
    exit 0
fi

trap 'exit 0' TERM INT
while :; do
    sleep 3600 &
    wait $!
done
