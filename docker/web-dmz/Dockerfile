ARG NGINX_IMAGE=nginx:1.28-alpine
FROM ${NGINX_IMAGE}

LABEL org.opencontainers.image.title="web-dmz" \
      org.opencontainers.image.description="Serveur web Nginx de la DMZ"

RUN apk upgrade --no-cache && apk add --no-cache iproute2 netcat-openbsd

COPY common/netinit.sh /usr/local/bin/netinit
COPY web-dmz/entrypoint.sh /netdevops-entrypoint.sh
RUN chmod 0755 /usr/local/bin/netinit /netdevops-entrypoint.sh

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1

ENTRYPOINT ["/netdevops-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
