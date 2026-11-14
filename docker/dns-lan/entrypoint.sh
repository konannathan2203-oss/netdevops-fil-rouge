#!/bin/sh
set -eu
netinit
exec dnsmasq --keep-in-foreground --conf-file=/etc/dnsmasq.d/netdevops.conf
