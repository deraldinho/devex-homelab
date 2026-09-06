FROM docker:28-cli AS dockercli
FROM eclipse-temurin:26-jdk-noble AS base
ARG RUNNER_VERSION=2.337.0
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git jq python3 python3-pip ant sudo \
    libicu74 libssl3 zlib1g \
 && rm -rf /var/lib/apt/lists/*
COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=dockercli /usr/local/libexec/docker/cli-plugins/docker-compose /usr/local/lib/docker/cli-plugins/docker-compose
RUN useradd -m -u 1001 runner \
 && mkdir -p /opt/runner-dist /runner \
 && curl -fsSL "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz" \
    | tar -xz -C /opt/runner-dist \
 && chown -R runner:runner /opt/runner-dist /runner
COPY runner-entrypoint.sh /usr/local/bin/runner-entrypoint.sh
RUN chmod 0755 /usr/local/bin/runner-entrypoint.sh

FROM base AS l2jtoren
USER runner
WORKDIR /runner
ENTRYPOINT ["/usr/local/bin/runner-entrypoint.sh"]

FROM base AS homelab
USER runner
WORKDIR /runner
ENTRYPOINT ["/usr/local/bin/runner-entrypoint.sh"]
