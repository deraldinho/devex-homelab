from __future__ import annotations

import argparse
import json
import string
from dataclasses import asdict, replace
from pathlib import Path

from .certificacao_cognitiva import CertificadorCognitivo
from .config_hermes import load_hermes_config
from .fontes_fisicas_cognitivas import descobrir_fonte_termica
from .hermes_adapter import HermesAdapter
from .modelo_llm_gateway import SolicitacaoInferencia
from .saida_cognitiva import parse_resposta_llm
from .sampler_linux_cognitivo import LinuxCognitiveSampler


def _sha40(valor: str) -> str:
    texto = valor.strip().lower()
    if len(texto) != 40 or any(c not in string.hexdigits.lower() for c in texto):
        raise argparse.ArgumentTypeError("expected-sha deve ser SHA-1 hexadecimal de 40 chars")
    return texto


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Atlas C5 Hermes physical certification runner")
    parser.add_argument("--expected-sha", required=True, type=_sha40)
    parser.add_argument("--hermes-config", required=True, type=Path)
    parser.add_argument("--timeout-s", type=float, default=20.0)
    return parser


def executar(args: argparse.Namespace) -> dict[str, object]:
    if float(args.timeout_s) <= 0:
        raise ValueError("timeout-s deve ser > 0")
    fonte = descobrir_fonte_termica()
    if fonte is None:
        raise RuntimeError("fonte termica nao encontrada")
    config = load_hermes_config(args.hermes_config)
    backend = HermesAdapter(replace(config, timeout_s=float(args.timeout_s)))
    sampler = LinuxCognitiveSampler(thermal_path=fonte.path)
    cert = CertificadorCognitivo(sampler=sampler)
    solicitacao = SolicitacaoInferencia(
        1,
        "certificacao_c5_fisica",
        '{"tipo":"certificacao_fisica","estado":"observado"}',
        config.max_context_tokens,
        "off",
    )

    def inferencia() -> dict[str, object]:
        resultado = backend.inferir(solicitacao)
        if not resultado.sucesso or resultado.texto is None:
            return {"sucesso": False, "tokens_por_s": resultado.tokens_por_s}
        parse_resposta_llm(resultado.texto)
        return {"sucesso": True, "tokens_por_s": resultado.tokens_por_s}

    resultado = cert.executar(inferencia)
    return {
        "schema_version": 2,
        "expected_sha": args.expected_sha,
        "backend": f"hermes/{config.provider}",
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
