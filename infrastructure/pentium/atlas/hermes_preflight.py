from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass

from .config_hermes import HermesConfig


_TOOL_COUNT = re.compile(r"Tool schemas.*\((\d+) tools\)", re.IGNORECASE)


@dataclass(frozen=True)
class HermesPreflightResult:
    ok: bool
    reason: str | None
    tool_count: int | None


class HermesPreflight:
    def __init__(self, config: HermesConfig, *, runner=subprocess.run):
        self._config = config
        self._runner = runner

    def _run(self, command: list[str]):
        try:
            return self._runner(
                command, capture_output=True, text=True, encoding="utf-8",
                errors="strict", timeout=10.0, check=False,
            )
        except (OSError, UnicodeError, subprocess.TimeoutExpired):
            return None
    def check(self) -> HermesPreflightResult:
        profile = self._run([
            self._config.binary, "profile", "show", self._config.profile,
        ])
        if profile is None or profile.returncode != 0:
            return HermesPreflightResult(False, "profile_unavailable", None)

        prompt_size = self._run([
            self._config.binary, "-p", self._config.profile, "prompt-size",
        ])
        if prompt_size is None or prompt_size.returncode != 0:
            return HermesPreflightResult(False, "prompt_size_unavailable", None)

        match = _TOOL_COUNT.search(prompt_size.stdout or "")
        if match is None:
            return HermesPreflightResult(False, "tool_count_unparseable", None)
        tool_count = int(match.group(1))
        if tool_count != 0:
            return HermesPreflightResult(False, "tools_enabled", tool_count)
        return HermesPreflightResult(True, None, tool_count)


def main() -> int:
    from pathlib import Path
    from .config_hermes import load_hermes_config

    cfg = load_hermes_config(Path(__file__).with_name("config_hermes.json"))
    result = HermesPreflight(cfg).check()
    print("ATLAS_HERMES_PREFLIGHT_PASS" if result.ok else f"ATLAS_HERMES_PREFLIGHT_FAIL:{result.reason}")
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
