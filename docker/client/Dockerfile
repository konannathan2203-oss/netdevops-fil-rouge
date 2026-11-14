ARG BASE_IMAGE=alpine:3.22
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="client" \
      org.opencontainers.image.description="Poste client de test (LAN) et outil de routage"

RUN apk upgrade --no-cache && apk add --no-cache curl bind-tools nmap iproute2 netcat-openbsd

COPY common/netinit.sh /usr/local/bin/netinit
COPY client/entrypoint.sh /entrypoint.sh
RUN chmod 0755 /usr/local/bin/netinit /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
