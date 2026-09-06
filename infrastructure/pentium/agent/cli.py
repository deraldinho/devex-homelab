#!/usr/bin/env python3
"""Command-line entrypoint for the allowlisted Pentium Agent."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from .actions.x99_status import collect_x99_status
    from .agent import Agent, UnknownActionError
    from .managed_inventory import ManagedHost, ManagedInventory
    from .managed_read import ManagedReadService
    from .ssh_transport import SshTransport
except ImportError:
    from actions.x99_status import collect_x99_status
    from agent import Agent, UnknownActionError
    from managed_inventory import ManagedHost, ManagedInventory
    from managed_read import ManagedReadService
    from ssh_transport import SshTransport


def load_config(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 2:
        raise ValueError("agent config schema_version must be 2")
    hosts = payload.get("managed_hosts")
    if not isinstance(hosts, list) or not hosts:
        raise ValueError("managed_hosts must be a non-empty list")
    return payload

def _managed_host_from_config(item: dict) -> ManagedHost:
    return ManagedHost(
        host_id=str(item["host_id"]),
        enrollment=str(item["enrollment"]),
        user=str(item["user"]),
        host=str(item["host"]),
        identity_file=Path(str(item["identity_file"])).expanduser(),
        known_hosts_file=Path(str(item["known_hosts_file"])).expanduser(),
        platform=str(item["platform"]),
        allowed_reads=frozenset(str(value) for value in item["allowed_reads"]),
        connect_timeout_seconds=int(item.get("connect_timeout_seconds", 5)),
        max_output_bytes=int(item.get("max_output_bytes", 65536)),
    )


def build_agent(path: Path) -> Agent:
    config = load_config(path)
    inventory = ManagedInventory([
        _managed_host_from_config(item) for item in config["managed_hosts"]
    ])
    service = ManagedReadService(inventory, SshTransport())
    return Agent(x99_status_handler=lambda: collect_x99_status(service))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("action")
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.json"))
    return parser.parse_args(argv)

def main(argv: list[str] | None = None, *, agent: Agent | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        active_agent = agent or build_agent(args.config)
        result = active_agent.execute(args.action)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"PENTIUM AGENT: ERROR | {exc}", file=sys.stderr)
        return 2
    except UnknownActionError as exc:
        print(f"PENTIUM AGENT: ERROR | {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if result.get("status") == "healthy" else 1


if __name__ == "__main__":
    raise SystemExit(main())
