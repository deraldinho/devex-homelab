from __future__ import annotations

import argparse
import json
import os
from typing import Sequence

from .network_discovery import LinuxArpScanner


def build_report(scanner, interface: str) -> dict:
    devices = scanner.scan(interface)
    return {
        "zone": "WIFI_OBSERVED",
        "interface": interface,
        "device_count": len(devices),
        "devices": [
            {"mac": item.mac, "ipv4": item.ipv4}
            for item in devices
        ],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Atlas D1 single-shot Wi-Fi discovery smoke")
    parser.add_argument("--interface")
    return parser


def main(argv: Sequence[str] | None = None, *, scanner=None) -> int:
    parser = _parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    interface = args.interface or os.environ.get("ATLAS_WIFI_INTERFACE")
    if not interface:
        parser.error("--interface or ATLAS_WIFI_INTERFACE is required")
    report = build_report(scanner or LinuxArpScanner(), interface)
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
