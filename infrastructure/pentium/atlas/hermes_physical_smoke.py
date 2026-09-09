from __future__ import annotations

import argparse
import json
import string
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config_hermes import load_hermes_config
from .hermes_adapter import HermesAdapter
from .hermes_preflight import HermesPreflight
from .modelo_llm_gateway import SolicitacaoInferencia
from .saida_cognitiva import parse_resposta_llm


@dataclass(frozen=True)
class RuntimeCheck:
    ok: bool
    reason: str | None
    sha: str | None


def _sha40(value: str) -> str:
    text = value.strip().lower()
    if len(text) != 40 or any(c not in string.hexdigits.lower() for c in text):
        raise argparse.ArgumentTypeError("expected-sha deve ser SHA-1 hexadecimal de 40 chars")
    return text


class HermesPhysicalSmoke:
    def __init__(self, *, runner=subprocess.run):
        self._runner = runner
    def _run(self, command: list[str], *, timeout: float = 10.0):
        try:
            return self._runner(
                command, capture_output=True, text=True, encoding="utf-8",
                errors="strict", timeout=timeout, check=False,
            )
        except (OSError, UnicodeError, subprocess.TimeoutExpired):
            return None

    def check_runtime(self, *, repo_root: Path, expected_sha: str) -> RuntimeCheck:
        git = self._run(["git", "-C", str(repo_root), "rev-parse", "HEAD"])
        if git is None or git.returncode != 0:
            return RuntimeCheck(False, "sha_unavailable", None)
        sha = (git.stdout or "").strip().lower()
        if sha != expected_sha.strip().lower():
            return RuntimeCheck(False, "sha_mismatch", sha)

        voice = self._run(["systemctl", "--user", "is-active", "atlas-voice.service"])
        if voice is None:
            return RuntimeCheck(False, "voice_state_unavailable", sha)
        if voice.returncode == 0 or (voice.stdout or "").strip() == "active":
            return RuntimeCheck(False, "voice_active", sha)
        return RuntimeCheck(True, None, sha)

    def execute(self, *, repo_root: Path, expected_sha: str, hermes_config: Path) -> dict[str, object]:
        runtime = self.check_runtime(repo_root=repo_root, expected_sha=expected_sha)
        if not runtime.ok:
            return {"ok": False, "reason": runtime.reason, "sha": runtime.sha}
        config = load_hermes_config(hermes_config)
        preflight = HermesPreflight(config, runner=self._runner).check()
        if not preflight.ok:
            return {"ok": False, "reason": preflight.reason, "sha": runtime.sha}

        request = SolicitacaoInferencia(
            1,
            "smoke_fisico_hermes",
            '{"tipo":"smoke_fisico","estado":"observado"}',
            config.max_context_tokens,
            "off",
        )
        result = HermesAdapter(config, runner=self._runner).inferir(request)
        if not result.sucesso or result.texto is None:
            reason = result.erro.value if result.erro is not None else "inference_failed"
            return {"ok": False, "reason": reason, "sha": runtime.sha}
        try:
            parse_resposta_llm(result.texto)
        except (TypeError, ValueError, KeyError):
            return {"ok": False, "reason": "invalid_cognitive_json", "sha": runtime.sha}
        return {
            "ok": True,
            "sha": runtime.sha,
            "backend": result.backend,
            "profile": config.profile,
            "tool_count": preflight.tool_count,
            "voice_active": False,
        }

def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Atlas Hermes physical smoke")
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--expected-sha", required=True, type=_sha40)
    parser.add_argument("--hermes-config", required=True, type=Path)
    return parser


def main() -> int:
    args = construir_parser().parse_args()
    output = HermesPhysicalSmoke().execute(
        repo_root=args.repo_root.resolve(),
        expected_sha=args.expected_sha,
        hermes_config=args.hermes_config,
    )
    print(json.dumps(output, ensure_ascii=True, sort_keys=True, separators=(",", ":")))
    return 0 if output.get("ok") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
