#!/usr/bin/env python3
"""Health/reachability contract for the DevEx HomeLab management tailnet."""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REQUIRED_NODE_FIELDS = {
    "role",
    "tailscale_name",
    "tailscale_ipv4",
    "ssh_port",
    "required",
}


def load_inventory(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("inventory schema_version must be 1")
    nodes = payload.get("nodes")
    if not isinstance(nodes, dict) or not nodes:
        raise ValueError("inventory must contain nodes")
    for name, node in nodes.items():
        missing = REQUIRED_NODE_FIELDS.difference(node)
        if missing:
            raise ValueError(f"node {name!r} is missing: {sorted(missing)}")
    return payload


def _entry_to_observed(entry: dict[str, Any]) -> dict[str, Any] | None:
    hostname = entry.get("HostName")
    if not hostname:
        return None
    ipv4 = next(
        (ip for ip in entry.get("TailscaleIPs", []) if ":" not in ip),
        None,
    )
    return {
        "name": hostname,
        "online": bool(entry.get("Online", False)),
        "ipv4": ipv4,
    }


def index_tailscale_status(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    self_entry = _entry_to_observed(payload.get("Self", {}))
    if self_entry:
        indexed[self_entry["name"]] = self_entry
    peers = payload.get("Peer", {})
    if isinstance(peers, dict):
        for peer in peers.values():
            observed = _entry_to_observed(peer)
            if observed:
                indexed[observed["name"]] = observed
    return indexed


def tcp_probe(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def evaluate_node(
    name: str,
    config: dict[str, Any],
    tailnet: dict[str, dict[str, Any]],
    tcp_probe: Callable[[str, int, float], bool] = tcp_probe,
    timeout: float = 2.0,
) -> dict[str, Any]:
    observed = tailnet.get(config["tailscale_name"])
    tailscale_online = bool(observed and observed["online"])
    ipv4_matches = bool(
        observed and observed.get("ipv4") == config["tailscale_ipv4"]
    )
    ssh_reachable = tcp_probe(
        config["tailscale_ipv4"], int(config["ssh_port"]), timeout
    )
    status = (
        "healthy"
        if tailscale_online and ipv4_matches and ssh_reachable
        else "degraded"
    )
    return {
        "name": name,
        "role": config["role"],
        "required": bool(config["required"]),
        "expected_ipv4": config["tailscale_ipv4"],
        "observed_ipv4": observed.get("ipv4") if observed else None,
        "tailscale_online": tailscale_online,
        "ipv4_matches": ipv4_matches,
        "ssh_reachable": ssh_reachable,
        "status": status,
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    required = [item for item in results if item["required"]]
    healthy = all(item["status"] == "healthy" for item in required)
    return {
        "status": "healthy" if healthy else "degraded",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "nodes": results,
    }


def read_tailscale_status() -> dict[str, Any]:
    completed = subprocess.run(
        ["tailscale", "status", "--json"],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def render_text(summary: dict[str, Any]) -> str:
    parts = [f"NETWORK: {summary['status'].upper()}"]
    for node in summary["nodes"]:
        ts = "ok" if node["tailscale_online"] else "fail"
        ip = "ok" if node["ipv4_matches"] else "fail"
        ssh = "ok" if node["ssh_reachable"] else "fail"
        parts.append(
            f"{node['name']}={node['status'].upper()}(ts={ts} ip={ip} ssh={ssh})"
        )
    return " | ".join(parts)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path(__file__).with_name("inventory.json"),
    )
    parser.add_argument("--target", action="append", default=[])
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        inventory = load_inventory(args.inventory)
        status = index_tailscale_status(read_tailscale_status())
        names = args.target or list(inventory["nodes"])
        unknown = [name for name in names if name not in inventory["nodes"]]
        if unknown:
            raise ValueError(f"unknown target(s): {', '.join(unknown)}")
        results = [
            evaluate_node(
                name,
                inventory["nodes"][name],
                status,
                timeout=args.timeout,
            )
            for name in names
        ]
        summary = summarize(results)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        print(f"NETWORK: ERROR | {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(summary, ensure_ascii=True, indent=2))
    else:
        print(render_text(summary))
    return 0 if summary["status"] == "healthy" else 1


if __name__ == "__main__":
    raise SystemExit(main())
