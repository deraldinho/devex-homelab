"""Service entrypoint for CP-SENTRY-P4 Linux credential-verified local relay.

Only accepts signed service execution receipts from a configured Unix UID.
Never accepts model prompts, invokes controls, or loads private signing keys.
"""
from __future__ import annotations

import os
import signal
import socket
import sys
from pathlib import Path

from infrastructure.pentium.atlas.sentry_receipt_v2 import (
    Ed25519RecoveryVerifier, load_public_key_from_file, load_public_key_ring,
)
from infrastructure.pentium.atlas.sentry_receipt_relay import (
    RotatingReceiptJournal, ReceiptRelay, ReceiptRelayServer,
)


def build_relay(environ=None):
    env=os.environ if environ is None else environ
    if env.get("ATLAS_SENTRY_V2_RELAY_ENABLED")!="1":
        raise RuntimeError("sentry_relay_disabled")
    try:
        socket_path=Path(env["ATLAS_SENTRY_V2_RELAY_SOCKET"])
        journal_path=Path(env["ATLAS_SENTRY_V2_RELAY_ACTION_JOURNAL"])
        peer_uid=int(env["ATLAS_SENTRY_V2_RELAY_ALLOWED_UID"])
        socket_gid=int(env["ATLAS_SENTRY_V2_RELAY_GROUP_GID"])
        if os.name=="posix" and peer_uid==os.geteuid():
            # Production requires a distinct executor principal; never
            # silently accept the relay's own OS identity as an executor.
            raise RuntimeError("relay_executor_principal_not_isolated")
        if env.get("ATLAS_SENTRY_V2_TRUST_KEYRING_FILE"):
            roots=load_public_key_ring(
                env["ATLAS_SENTRY_V2_TRUST_KEYRING_FILE"])
        else:
            roots={
                "executor":{
                    env["ATLAS_SENTRY_V2_EXECUTOR_KEY_ID"]:
                    load_public_key_from_file(env["ATLAS_SENTRY_V2_EXECUTOR_PUBLIC_KEY_FILE"]),
                },
                "health_probe":{
                    env["ATLAS_SENTRY_V2_HEALTH_KEY_ID"]:
                    load_public_key_from_file(env["ATLAS_SENTRY_V2_HEALTH_PUBLIC_KEY_FILE"]),
                },
            }
    except (KeyError,ValueError,TypeError) as exc:
        raise RuntimeError("sentry_relay_trust_configuration_invalid") from exc
    verifier=Ed25519RecoveryVerifier(
        roots,trusted_host="pentium",
    )
    relay=ReceiptRelay(RotatingReceiptJournal(journal_path),verifier,
                       allowed_uid=peer_uid)
    return ReceiptRelayServer(socket_path,relay,group_id=socket_gid)


def main():
    try:
        server=build_relay()
    except Exception as exc:
        print("ATLAS_SENTRY_RELAY_STARTUP_FAILED type="+type(exc).__name__,flush=True)
        return 2
    running=True
    def stop(*_):
        nonlocal running
        running=False
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    try:
        with server:
            server._sock.settimeout(1)
            print("ATLAS_SENTRY_RELAY_READY",flush=True)
            metrics=os.environ.get("ATLAS_SENTRY_V2_RELAY_STATUS_FILE")
            if metrics:
                server.publish_status(Path(metrics))
            while running:
                try:
                    server.serve_one()
                    if metrics:
                        server.publish_status(Path(metrics))
                except socket.timeout:
                    continue
                except Exception as exc:
                    # A malformed or unauthorized message is isolated.
                    print("ATLAS_SENTRY_RELAY_EVENT_ERROR type="+type(exc).__name__,flush=True)
        return 0
    except Exception as exc:
        print("ATLAS_SENTRY_RELAY_FATAL type="+type(exc).__name__,flush=True)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
