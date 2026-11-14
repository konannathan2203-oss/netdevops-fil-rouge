ARG BASE_IMAGE=alpine:3.22
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="router-fw" \
      org.opencontainers.image.description="Routeur pare-feu nftables entre DMZ, LAN et Management"

RUN apk upgrade --no-cache && apk add --no-cache nftables iproute2 tcpdump

COPY common/netinit.sh /usr/local/bin/netinit
COPY router-fw/entrypoint.sh /entrypoint.sh
RUN chmod 0755 /usr/local/bin/netinit /entrypoint.sh

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD nft list table inet filter > /dev/null || exit 1

ENTRYPOINT ["/entrypoint.sh"]
