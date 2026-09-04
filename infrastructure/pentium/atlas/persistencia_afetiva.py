from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .decaimento_afetivo import decair_estado
from .modelo_afetivo import EstadoAfetivo, PersonalidadeBase, PoliticaDecaimento


class EstadoAfetivoSalvoInvalido(ValueError):
    pass


class OrigemRestauracaoAfetiva(str, Enum):
    ESTADO_SALVO = "estado_salvo"
    BASE_POR_AUSENCIA = "base_por_ausencia"
    BASE_POR_ESTADO_INVALIDO = "base_por_estado_invalido"


@dataclass(frozen=True)
class ResultadoRestauracaoAfetiva:
    estado: EstadoAfetivo
    origem: OrigemRestauracaoAfetiva
    erro: str | None = None


class RepositorioEstadoAfetivo:
    def __init__(self, caminho: Path):
        self._caminho = Path(caminho)

    def salvar(self, estado: EstadoAfetivo) -> None:
        self._caminho.parent.mkdir(parents=True, exist_ok=True)
        temporario = self._caminho.with_name(self._caminho.name + ".tmp")
        payload = {
            "versao_esquema": 1,
            "estado": {
                "valencia": estado.valencia,
                "ativacao": estado.ativacao,
                "estresse": estado.estresse,
                "confianca": estado.confianca,
                "engajamento": estado.engajamento,
                "curiosidade": estado.curiosidade,
                "atualizado_em": estado.atualizado_em,
                "foco_atencao": estado.foco_atencao,
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

    def carregar(self) -> EstadoAfetivo | None:
        if not self._caminho.exists():
            return None
        try:
            payload = json.loads(self._caminho.read_text(encoding="utf-8"))
            if payload.get("versao_esquema") != 1:
                raise ValueError("estado afetivo versao_esquema deve ser 1")
            return EstadoAfetivo(**payload["estado"])
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise EstadoAfetivoSalvoInvalido(str(exc)) from exc


def restaurar_estado(
    repositorio: RepositorioEstadoAfetivo,
    personalidade: PersonalidadeBase,
    politica: PoliticaDecaimento,
    agora: str,
) -> ResultadoRestauracaoAfetiva:
    try:
        estado = repositorio.carregar()
        if estado is None:
            return ResultadoRestauracaoAfetiva(
                personalidade.criar_estado(agora),
                OrigemRestauracaoAfetiva.BASE_POR_AUSENCIA,
            )
        restaurado = decair_estado(estado, personalidade, politica, agora, modo_offline=True)
        return ResultadoRestauracaoAfetiva(restaurado, OrigemRestauracaoAfetiva.ESTADO_SALVO)
    except (EstadoAfetivoSalvoInvalido, ValueError) as exc:
        return ResultadoRestauracaoAfetiva(
            personalidade.criar_estado(agora),
            OrigemRestauracaoAfetiva.BASE_POR_ESTADO_INVALIDO,
            str(exc),
        )
