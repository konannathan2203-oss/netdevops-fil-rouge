#!/bin/sh
# Demarrage du routeur : routes, puis chargement des regles nftables.
set -eu

netinit

if [ "$(cat /proc/sys/net/ipv4/ip_forward)" != "1" ]; then
    echo "[router-fw] ERREUR : ip_forward desactive" >&2
    exit 1
fi

nft --file /etc/nftables/nftables.conf
echo "[router-fw] regles nftables chargees :"
nft list ruleset

trap 'echo "[router-fw] arret"; exit 0' TERM INT
while :; do
    sleep 3600 &
    wait $!
done
