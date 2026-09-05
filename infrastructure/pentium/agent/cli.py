#!/usr/bin/env python3
"""Command-line entrypoint for the allowlisted Pentium Agent."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from actions.x99_status import collect_x99_status
from agent import Agent, UnknownActionError
from ssh_transport import SshTarget, SshTransport


def load_config(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or "x99" not in payload:
        raise ValueError("agent config schema is invalid")
    return payload


def build_agent(path: Path) -> Agent:
    config = load_config(path)
    x99 = config["x99"]
    target = SshTarget(
        user=str(x99["user"]),
        host=str(x99["host"]),
        identity_file=Path(str(x99["identity_file"])).expanduser(),
        connect_timeout_seconds=int(x99["connect_timeout_seconds"]),
    )
    transport = SshTransport()
    return Agent(
        x99_status_handler=lambda: collect_x99_status(transport, target),
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("action")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).with_name("config.json"),
    )
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
