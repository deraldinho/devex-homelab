from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from . import c5_physical_runner
from .llama_server_runtime import LlamaCppServerRuntime


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
    parser.add_argument("--context-size", type=int, default=4096)
    parser.add_argument("--cache-reuse", type=int, default=64)
    parser.add_argument("--timeout-s", type=float, default=20.0)
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
    try:
        while not args.socket.exists():
            if proc.poll() is not None:
                raise RuntimeError("llama-server encerrou antes de criar o socket")
            if time.monotonic() >= limite:
                raise TimeoutError("llama-server nao criou socket no prazo")
            time.sleep(0.1)
        runner_args = argparse.Namespace(
            llm_pid=proc.pid,
            socket=args.socket,
            expected_sha=esperado,
            timeout_s=args.timeout_s,
            cache_reuse=args.cache_reuse,
            max_response_bytes=args.max_response_bytes,
        )
        evidencia = c5_physical_runner.executar(runner_args)
        evidencia["orchestrator"] = {
            "schema_version": 1,
            "repo_root": str(repo_root),
            "llama_server": str(args.llama_server),
            "model": str(args.model),
            "context_size": args.context_size,
            "cache_reuse": args.cache_reuse,
        }
        return evidencia
    finally:
        runtime.stop()


def main() -> int:
    args = construir_parser().parse_args()
    evidencia = executar(args)
    print(json.dumps(evidencia, ensure_ascii=True, sort_keys=True, separators=(",", ":")))
    return 0 if evidencia["resultado"]["inferencia_sucesso"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
