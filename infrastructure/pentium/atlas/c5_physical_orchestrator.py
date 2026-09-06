from __future__ import annotations

import argparse
import json
import subprocess
import time
from dataclasses import asdict
from pathlib import Path

from . import c5_physical_runner
from .c5_observation_probe import C5ObservationProbe
from .c5_physical_campaign import executar_campanha_c5
from .llama_server_runtime import LlamaCppServerRuntime
from .unix_http import get_json_unix


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
    parser = argparse.ArgumentParser(description="Atlas C5 physical orchestrator")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--llama-server", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--heartbeat-state", type=Path, required=True)
    parser.add_argument("--heartbeat-max-age-s", type=float, required=True)
    parser.add_argument("--soak-iterations", type=int, required=True)
    parser.add_argument("--context-size", type=int, default=4096)
    parser.add_argument("--cache-reuse", type=int, default=64)
    parser.add_argument("--timeout-s", type=float, default=20.0)
    parser.add_argument("--timeout-probe-s", type=float, default=0.001)
    parser.add_argument("--startup-timeout-s", type=float, default=10.0)
    parser.add_argument("--max-response-bytes", type=int, default=8192)
    return parser


def executar(args: argparse.Namespace) -> dict[str, object]:
    repo_root = args.repo_root.resolve()
    esperado = args.expected_sha.strip().lower()
    if _sha_local(repo_root) != esperado:
        raise RuntimeError("HEAD local difere do expected-sha")
    if not args.llama_server.is_file():
        raise FileNotFoundError("llama-server nao encontrado")
    if not args.model.is_file():
        raise FileNotFoundError("modelo GGUF nao encontrado")
    if not args.heartbeat_state.expanduser().is_file():
        raise FileNotFoundError("heartbeat state nao encontrado")
    if not str(args.socket).endswith(".sock"):
        raise ValueError("socket deve terminar em .sock")
    if args.socket.exists():
        raise RuntimeError("socket ja existe; recusar sobrescrever runtime possivelmente ativo")
    if args.startup_timeout_s <= 0:
        raise ValueError("startup-timeout-s deve ser > 0")

    runtime = LlamaCppServerRuntime(
        args.llama_server,
        args.model,
        args.socket,
        context_size=args.context_size,
        cache_reuse=args.cache_reuse,
    )
    proc = runtime.start()
    limite = time.monotonic() + args.startup_timeout_s
    observation_probe = None
    try:
        while not args.socket.exists():
            if proc.poll() is not None:
                raise RuntimeError("llama-server encerrou antes de criar o socket")
            if time.monotonic() >= limite:
                raise TimeoutError("llama-server nao criou socket no prazo")
            time.sleep(0.1)

        while True:
            if proc.poll() is not None:
                raise RuntimeError("llama-server encerrou antes do readiness")
            if time.monotonic() >= limite:
                raise TimeoutError("llama-server nao ficou ready no prazo")
            try:
                status, health = get_json_unix(args.socket, "/health", 1.0, 1024)
                if status == 200 and health.get("status") == "ok":
                    break
            except Exception:
                pass
            time.sleep(0.1)

        observation_probe = C5ObservationProbe(
            args.heartbeat_state,
            max_age_s=args.heartbeat_max_age_s,
        )

        def run_once(*, timeout_s: float, fase: str) -> dict[str, object]:
            runner_args = argparse.Namespace(
                llm_pid=proc.pid,
                socket=args.socket,
                expected_sha=esperado,
                timeout_s=timeout_s,
                cache_reuse=args.cache_reuse,
                max_response_bytes=args.max_response_bytes,
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
            "schema_version": 2,
            "campaign": asdict(campanha),
            "orchestrator": {
                "repo_root": str(repo_root),
                "llama_server": str(args.llama_server),
                "model": str(args.model),
                "context_size": args.context_size,
                "cache_reuse": args.cache_reuse,
                "heartbeat_state": str(args.heartbeat_state.expanduser()),
                "heartbeat_max_age_s": args.heartbeat_max_age_s,
            },
        }
    finally:
        if observation_probe is not None:
            observation_probe.close()
        runtime.stop()


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
