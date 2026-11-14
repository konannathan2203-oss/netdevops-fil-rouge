#!/bin/sh
# Applique les routes reseau passees dans la variable NET_ROUTES.
# Format : "destination via passerelle;destination via passerelle"
# Exemple : NET_ROUTES="default via 172.20.2.1"
set -eu

if [ -n "${NET_ROUTES:-}" ]; then
    echo "${NET_ROUTES}" | tr ';' '\n' | while read -r route; do
        [ -z "${route}" ] && continue
        # shellcheck disable=SC2086
        ip route replace ${route}
        echo "[netinit] route appliquee : ${route}"
    done
fi
echo "[netinit] table de routage :"
ip route
