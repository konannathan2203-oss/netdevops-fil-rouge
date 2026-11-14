ARG BASE_IMAGE=alpine:3.22
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="dns-lan" \
      org.opencontainers.image.description="Serveur DNS dnsmasq du LAN"

RUN apk upgrade --no-cache && apk add --no-cache dnsmasq iproute2 bind-tools

COPY common/netinit.sh /usr/local/bin/netinit
COPY dns-lan/entrypoint.sh /entrypoint.sh
RUN chmod 0755 /usr/local/bin/netinit /entrypoint.sh

EXPOSE 53/udp 53/tcp

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD pgrep dnsmasq > /dev/null || exit 1

ENTRYPOINT ["/entrypoint.sh"]
