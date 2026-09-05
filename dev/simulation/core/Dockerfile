FROM ubuntu:26.04

RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates \
      netcat-openbsd \
      socat \
 && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /workspace /state \
 && chown -R ubuntu:ubuntu /state

COPY entrypoint.sh /usr/local/bin/sim-core-entrypoint
RUN chmod 0755 /usr/local/bin/sim-core-entrypoint

USER 1000:1000
WORKDIR /workspace

ENV DEVEX_NODE_NAME=sim-core
ENV DEVEX_NODE_ROLE=homelab.compute

ENTRYPOINT ["/usr/local/bin/sim-core-entrypoint"]
