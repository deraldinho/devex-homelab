from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .modelo_incidente import EstadoRecuperacaoIncidente, IncidenteTecnico
from .modelo_percepcao import EstadoObservacao, EstadoPercepcao


class OrigemRestauracaoPercepcaoCorrelacao(str, Enum):
    ESTADO_SALVO = "estado_salvo"
    BASE_POR_AUSENCIA = "base_por_ausencia"
    BASE_POR_ESTADO_INVALIDO = "base_por_estado_invalido"


@dataclass(frozen=True)
class ResultadoRestauracaoPercepcaoCorrelacao:
    percepcoes: tuple[EstadoPercepcao, ...]
    incidentes: tuple[IncidenteTecnico, ...]
    origem: OrigemRestauracaoPercepcaoCorrelacao
    erro: str | None = None


class RepositorioPercepcaoCorrelacao:
    def __init__(self, caminho: Path):
        self._caminho = Path(caminho)

    def salvar(self, percepcoes, incidentes) -> None:
        self._caminho.parent.mkdir(parents=True, exist_ok=True)
        temporario = self._caminho.with_name(self._caminho.name + ".tmp")
        payload = {
            "versao_esquema": 1,
            "percepcoes": [self._serializar_percepcao(item) for item in sorted(percepcoes, key=lambda p: p.entidade_id)],
            "incidentes": [self._serializar_incidente(item) for item in sorted(incidentes, key=lambda i: i.incidente_id)],
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

    def restaurar(self) -> ResultadoRestauracaoPercepcaoCorrelacao:
        if not self._caminho.exists():
            return ResultadoRestauracaoPercepcaoCorrelacao(
                (), (), OrigemRestauracaoPercepcaoCorrelacao.BASE_POR_AUSENCIA
            )
        try:
            payload = json.loads(self._caminho.read_text(encoding="utf-8"))
            if payload.get("versao_esquema") != 1:
                raise ValueError("versao_esquema deve ser 1")
            percepcoes = tuple(self._desserializar_percepcao(item) for item in payload["percepcoes"])
            incidentes = tuple(self._desserializar_incidente(item) for item in payload["incidentes"])
            return ResultadoRestauracaoPercepcaoCorrelacao(
                percepcoes, incidentes, OrigemRestauracaoPercepcaoCorrelacao.ESTADO_SALVO
            )
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            return ResultadoRestauracaoPercepcaoCorrelacao(
                (), (), OrigemRestauracaoPercepcaoCorrelacao.BASE_POR_ESTADO_INVALIDO, str(exc)
            )

    @staticmethod
    def _serializar_percepcao(item: EstadoPercepcao) -> dict:
        return {
            "entidade_id": item.entidade_id,
            "estado": item.estado.value,
            "confianca": item.confianca,
            "ultima_observacao_valida": item.ultima_observacao_valida,
            "fontes_disponiveis": list(item.fontes_disponiveis),
            "fontes_indisponiveis": list(item.fontes_indisponiveis),
            "conflito_evidencias": item.conflito_evidencias,
            "atualizado_em": item.atualizado_em,
        }

    @staticmethod
    def _desserializar_percepcao(item: dict) -> EstadoPercepcao:
        return EstadoPercepcao(
            entidade_id=item["entidade_id"],
            estado=EstadoObservacao(item["estado"]),
            confianca=item["confianca"],
            ultima_observacao_valida=item["ultima_observacao_valida"],
            fontes_disponiveis=tuple(item["fontes_disponiveis"]),
            fontes_indisponiveis=tuple(item["fontes_indisponiveis"]),
            conflito_evidencias=item["conflito_evidencias"],
            atualizado_em=item["atualizado_em"],
        )

    @staticmethod
    def _serializar_incidente(item: IncidenteTecnico) -> dict:
        return {
            "incidente_id": item.incidente_id,
            "entidade_principal": item.entidade_principal,
            "tipo": item.tipo,
            "gravidade": item.gravidade,
            "inicio_em": item.inicio_em,
            "causa_provavel": item.causa_provavel,
            "confianca_causal": item.confianca_causal,
            "entidades_afetadas": list(item.entidades_afetadas),
            "total_entidades_afetadas": item.total_entidades_afetadas,
            "eventos_correlacionados": list(item.eventos_correlacionados),
            "estado_recuperacao": item.estado_recuperacao.value,
            "recuperado_em": item.recuperado_em,
        }

    @staticmethod
    def _desserializar_incidente(item: dict) -> IncidenteTecnico:
        return IncidenteTecnico(
            incidente_id=item["incidente_id"],
            entidade_principal=item["entidade_principal"],
            tipo=item["tipo"],
            gravidade=item["gravidade"],
            inicio_em=item["inicio_em"],
            causa_provavel=item["causa_provavel"],
            confianca_causal=item["confianca_causal"],
            entidades_afetadas=tuple(item["entidades_afetadas"]),
            total_entidades_afetadas=item["total_entidades_afetadas"],
            eventos_correlacionados=tuple(item.get("eventos_correlacionados", ())),
            estado_recuperacao=EstadoRecuperacaoIncidente(item["estado_recuperacao"]),
            recuperado_em=item.get("recuperado_em"),
        )
