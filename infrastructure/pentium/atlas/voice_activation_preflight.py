from __future__ import annotations

import os
import re
from pathlib import Path

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_REQUIRED_DEVICES = ("controlC0", "pcmC0D0c", "pcmC0D0p")
_REQUIRED_TOOLS = (
    "runtime/whisper/build/bin/whisper-cli",
    "runtime/espeak-root/usr/bin/espeak-ng",
    "runtime/alsa-root/usr/bin/arecord",
    "runtime/alsa-root/usr/bin/aplay",
)


class VoiceActivationPreflight:
    def __init__(self, agent_root: Path, *, device_root: Path = Path("/dev/snd")):
        self.agent_root = Path(agent_root)
        self.device_root = Path(device_root)

    @staticmethod
    def _group_names() -> set[str]:
        import grp
        gids = set(os.getgroups()) | {os.getgid()}
        names = set()
        for gid in gids:
            try:
                names.add(grp.getgrgid(gid).gr_name)
            except KeyError:
                continue
        return names
    @staticmethod
    def _has_rw_access(path: Path) -> bool:
        return path.exists() and os.access(path, os.R_OK | os.W_OK)

    @staticmethod
    def _is_executable(path: Path) -> bool:
        return path.is_file() and os.access(path, os.X_OK)

    def run(self, expected_sha: str, *, groups: set[str] | None = None) -> dict:
        expected = str(expected_sha).strip().lower()
        deployed_path = self.agent_root / "atlas" / "runtime" / "deployed-sha"
        deployed = deployed_path.read_text(encoding="utf-8").strip().lower() if deployed_path.is_file() else ""
        group_names = self._group_names() if groups is None else set(groups)

        checks = {
            "sha_format": bool(_SHA_RE.fullmatch(expected)),
            "exact_sha": bool(expected) and deployed == expected,
            "audio_group": "audio" in group_names,
        }
        for name in _REQUIRED_DEVICES:
            checks[f"device_{name}"] = self._has_rw_access(self.device_root / name)
        for rel in _REQUIRED_TOOLS:
            checks[f"tool_{Path(rel).name}"] = self._is_executable(self.agent_root / rel)

        return {
            "schema_version": 1,
            "expected_sha": expected,
            "ready": all(checks.values()),
            "checks": checks,
        }
