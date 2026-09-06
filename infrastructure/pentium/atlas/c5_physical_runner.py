from __future__ import annotations

import argparse
import json
import string
from dataclasses import asdict
from pathlib import Path

from .certificacao_cognitiva import CertificadorCognitivo
from .fontes_fisicas_cognitivas import descobrir_fonte_termica, status_path_para_pid
from .llama_cpp_resident_backend import LlamaCppResidentBackend
from .modelo_llm_gateway import SolicitacaoInferencia
from .saida_cognitiva import parse_resposta_llm
from .sampler_linux_cognitivo import LinuxCognitiveSampler


def _pid_positivo(valor: str) -> int:
    pid = int(valor)
    if pid <= 0:
        raise argparse.ArgumentTypeError("llm-pid deve ser > 0")
    return pid


def _sha40(valor: str) -> str:
    texto = valor.strip().lower()
    if len(texto) != 40 or any(c not in string.hexdigits.lower() for c in texto):
        raise argparse.ArgumentTypeError("expected-sha deve ser SHA-1 hexadecimal de 40 chars")
    return texto


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Atlas C5 physical certification runner")
    parser.add_argument("--llm-pid", required=True, type=_pid_positivo)
    parser.add_argument("--socket", required=True, type=Path)
    parser.add_argument("--expected-sha", required=True, type=_sha40)
    parser.add_argument("--timeout-s", type=float, default=20.0)
    parser.add_argument("--cache-reuse", type=int, default=64)
    parser.add_argument("--max-response-bytes", type=int, default=8192)
    return parser


def executar(args: argparse.Namespace) -> dict[str, object]:
    if not str(args.socket).endswith(".sock"):
        raise ValueError("socket deve terminar em .sock")
    fonte = descobrir_fonte_termica()
    if fonte is None:
        raise RuntimeError("fonte termica nao encontrada")
    sampler = LinuxCognitiveSampler(
        thermal_path=fonte.path,
        llm_status_path=status_path_para_pid(args.llm_pid),
    )
    backend = LlamaCppResidentBackend(
        args.socket,
        cache_reuse=args.cache_reuse,
        timeout_s=args.timeout_s,
        max_response_bytes=args.max_response_bytes,
        fallback=None,
    )
    cert = CertificadorCognitivo(sampler=sampler)
    solicitacao = SolicitacaoInferencia(
        1,
        "certificacao_c5_fisica",
        '{"tipo":"certificacao_fisica","estado":"observado"}',
        4096,
    )

    def inferencia() -> dict[str, object]:
        resultado = backend.inferir(solicitacao)
        if not resultado.sucesso or resultado.texto is None:
            return {"sucesso": False, "tokens_por_s": resultado.tokens_por_s}
        parse_resposta_llm(resultado.texto)
        return {"sucesso": True, "tokens_por_s": resultado.tokens_por_s}

    resultado = cert.executar(inferencia)
    return {
        "schema_version": 1,
        "expected_sha": args.expected_sha,
        "llm_pid": args.llm_pid,
        "socket": str(args.socket),
        "thermal_type": fonte.tipo,
        "thermal_path": str(fonte.path),
        "resultado": asdict(resultado),
    }


def main() -> int:
    args = construir_parser().parse_args()
    saida = executar(args)
    print(json.dumps(saida, ensure_ascii=True, sort_keys=True, separators=(",", ":")))
    return 0 if saida["resultado"]["inferencia_sucesso"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
