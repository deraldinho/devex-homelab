from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict
from pathlib import Path

from . import c5_physical_runner
from .c5_observation_probe import C5ObservationProbe
from .c5_physical_campaign import executar_campanha_c5
from .config_hermes import load_hermes_config
from .hermes_adapter import HermesAdapter


def _sha_local(repo_root: Path) -> str:
    concluido = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )
    return concluido.stdout.strip().lower()


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Atlas C5 Hermes physical orchestrator")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--hermes-config", type=Path, required=True)
    parser.add_argument("--heartbeat-state", type=Path, required=True)
    parser.add_argument("--heartbeat-max-age-s", type=float, required=True)
    parser.add_argument("--soak-iterations", type=int, required=True)
    parser.add_argument("--timeout-s", type=float, default=20.0)
    parser.add_argument("--timeout-probe-s", type=float, default=0.001)
    return parser


def executar(args: argparse.Namespace) -> dict[str, object]:
    repo_root = args.repo_root.resolve()
    esperado = args.expected_sha.strip().lower()
    if _sha_local(repo_root) != esperado:
        raise RuntimeError("HEAD local difere do expected-sha")
    if not args.heartbeat_state.expanduser().is_file():
        raise FileNotFoundError("heartbeat state nao encontrado")
    config = load_hermes_config(args.hermes_config)
    HermesAdapter(config)
    observation_probe = C5ObservationProbe(
        args.heartbeat_state,
        max_age_s=args.heartbeat_max_age_s,
    )

    try:
        def run_once(*, timeout_s: float, fase: str) -> dict[str, object]:
            runner_args = argparse.Namespace(
                expected_sha=esperado,
                hermes_config=args.hermes_config,
                timeout_s=timeout_s,
            )
            evidencia = c5_physical_runner.executar(runner_args)
            evidencia["fase"] = fase
            return evidencia

        campanha = executar_campanha_c5(
            expected_sha=esperado,
            run_once=run_once,
            observation_probe=observation_probe,
            timeout_normal_s=args.timeout_s,
            timeout_probe_s=args.timeout_probe_s,
            soak_iteracoes=args.soak_iterations,
        )
        return {
            "schema_version": 3,
            "campaign": asdict(campanha),
            "orchestrator": {
                "repo_root": str(repo_root),
                "backend": f"hermes/{config.provider}",
                "profile": config.profile,
                "heartbeat_state": str(args.heartbeat_state.expanduser()),
                "heartbeat_max_age_s": args.heartbeat_max_age_s,
            },
        }
    finally:
        observation_probe.close()


def main() -> int:
    args = construir_parser().parse_args()
    evidencia = executar(args)
    print(json.dumps(evidencia, ensure_ascii=True, sort_keys=True, separators=(",", ":")))
    campanha = evidencia["campaign"]
    cold_ok = bool(campanha["cold"].get("inferencia_sucesso"))
    warm_ok = bool(campanha["warm"].get("inferencia_sucesso"))
    coleta_ok = (
        cold_ok
        and warm_ok
        and bool(campanha["timeout_isolado"])
        and bool(campanha["observation_runtime_preservado"])
        and int(campanha["soak_falhas"]) == 0
    )
    return 0 if coleta_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
