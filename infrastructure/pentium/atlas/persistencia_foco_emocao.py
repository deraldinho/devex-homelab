from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from .contexto_foco_emocao import ResultadoFocoEmocao
from .emocao_derivada import EmocaoDerivada
from .modelo_afetivo import EstadoAfetivo
from .modelo_foco import AssuntoFoco, FocoAtencao


@dataclass(frozen=True)
class ResultadoRestauracaoFocoEmocao:
    snapshot: ResultadoFocoEmocao | None
    origem: str
    erro: str | None = None


def _assunto_para_dict(item: AssuntoFoco) -> dict:
    return {
        "assunto_id": item.assunto_id,
        "entidade_id": item.entidade_id,
        "gravidade": item.gravidade,
        "impacto_afetivo": item.impacto_afetivo,
        "importancia": item.importancia,
        "novidade": item.novidade,
        "urgencia": item.urgencia,
        "recencia": item.recencia,
        "critico": item.critico,
        "recuperado": item.recuperado,
    }


def _assunto_de_dict(item: dict) -> AssuntoFoco:
    return AssuntoFoco(
        assunto_id=item["assunto_id"],
        entidade_id=item["entidade_id"],
        gravidade=item["gravidade"],
        impacto_afetivo=item["impacto_afetivo"],
        importancia=item["importancia"],
        novidade=item["novidade"],
        urgencia=item["urgencia"],
        recencia=item["recencia"],
        critico=item.get("critico", False),
        recuperado=item.get("recuperado", False),
    )


def _estado_para_dict(item: EstadoAfetivo) -> dict:
    return {
        "valencia": item.valencia,
        "ativacao": item.ativacao,
        "estresse": item.estresse,
        "confianca": item.confianca,
        "engajamento": item.engajamento,
        "curiosidade": item.curiosidade,
        "atualizado_em": item.atualizado_em,
        "foco_atencao": item.foco_atencao,
    }


def _estado_de_dict(item: dict) -> EstadoAfetivo:
    return EstadoAfetivo(
        valencia=item["valencia"],
        ativacao=item["ativacao"],
        estresse=item["estresse"],
        confianca=item["confianca"],
        engajamento=item["engajamento"],
        curiosidade=item["curiosidade"],
        atualizado_em=item["atualizado_em"],
        foco_atencao=item.get("foco_atencao"),
    )


class RepositorioFocoEmocao:
    def __init__(self, caminho: Path):
        self._caminho = Path(caminho)

    def salvar(self, snapshot: ResultadoFocoEmocao) -> None:
        self._caminho.parent.mkdir(parents=True, exist_ok=True)
        temporario = self._caminho.with_name(self._caminho.name + ".tmp")
        payload = {
            "versao_esquema": 1,
            "estado_afetivo": _estado_para_dict(snapshot.estado_afetivo),
            "foco": {
                "principal": _assunto_para_dict(snapshot.foco.principal) if snapshot.foco.principal else None,
                "secundarios": [_assunto_para_dict(item) for item in snapshot.foco.secundarios],
                "atualizado_em": snapshot.foco.atualizado_em,
                "capacidade_secundarios": snapshot.foco.capacidade_secundarios,
            },
            "emocao": {
                "principal": snapshot.emocao.principal,
                "nuances": list(snapshot.emocao.nuances),
            },
        }
        try:
            with temporario.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporario, self._caminho)
            if os.name == "posix" and hasattr(os, "O_DIRECTORY"):
                fd = os.open(self._caminho.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
        finally:
            temporario.unlink(missing_ok=True)

    def carregar(self) -> ResultadoFocoEmocao | None:
        if not self._caminho.exists():
            return None
        payload = json.loads(self._caminho.read_text(encoding="utf-8"))
        if payload.get("versao_esquema") != 1:
            raise ValueError("versao_esquema deve ser 1")
        foco_raw = payload["foco"]
        principal_raw = foco_raw.get("principal")
        foco = FocoAtencao(
            principal=_assunto_de_dict(principal_raw) if principal_raw else None,
            secundarios=tuple(_assunto_de_dict(item) for item in foco_raw["secundarios"]),
            atualizado_em=foco_raw["atualizado_em"],
            capacidade_secundarios=foco_raw["capacidade_secundarios"],
        )
        emocao_raw = payload["emocao"]
        emocao = EmocaoDerivada(
            principal=emocao_raw["principal"],
            nuances=tuple(emocao_raw.get("nuances", ())),
        )
        return ResultadoFocoEmocao(
            estado_afetivo=_estado_de_dict(payload["estado_afetivo"]),
            foco=foco,
            emocao=emocao,
        )


def restaurar_foco_emocao(repo: RepositorioFocoEmocao) -> ResultadoRestauracaoFocoEmocao:
    try:
        snapshot = repo.carregar()
        if snapshot is None:
            return ResultadoRestauracaoFocoEmocao(None, "ausente")
        return ResultadoRestauracaoFocoEmocao(snapshot, "estado_salvo")
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        return ResultadoRestauracaoFocoEmocao(None, "invalido", str(exc))
