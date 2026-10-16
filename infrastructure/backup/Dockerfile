# Restic image pinned to digest verified on core on 2026-10-13.
# Build-only contract: do not install or enable systemd timers automatically.
FROM restic/restic:0.17.3@sha256:8f5a62b422a2cb1277ea0dd6e826fe1acf649e5b9f02d60e5268d5fd1976255a

# The upstream image does not include python3/sqlite3/curl, required by
# our backup/verification scripts; openssh-client is for an approved SFTP repo.
RUN apk add --no-cache python3 sqlite curl ca-certificates openssh-client

COPY --chown=65534:65534 restic-backup.sh restic-verify.sh sqlite_snapshot.py verify_sqlite_restore.py github-sync.sh /scripts/
ENV PYTHONDONTWRITEBYTECODE=1
USER 65534:65534

ENTRYPOINT ["/bin/sh", "/scripts/restic-backup.sh"]
