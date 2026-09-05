FROM ubuntu:26.04

RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates \
      netcat-openbsd \
 && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /workspace /state \
 && chown -R ubuntu:ubuntu /state

COPY entrypoint.sh /usr/local/bin/sim-pentium-entrypoint
RUN chmod 0755 /usr/local/bin/sim-pentium-entrypoint

USER 1000:1000
WORKDIR /workspace

ENV DEVEX_NODE_NAME=sim-pentium
ENV DEVEX_NODE_ROLE=homelab.control

ENTRYPOINT ["/usr/local/bin/sim-pentium-entrypoint"]
