from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


class MotivoAtivacaoCognitiva(str, Enum):
    CRITICIDADE_TECNICA = "criticidade_tecnica"
    NOVIDADE_RELEVANTE = "novidade_relevante"
    MUDANCA_ESTADO = "mudanca_estado"
    MUDANCA_AFETIVA = "mudanca_afetiva"
    RECUPERACAO_IMPORTANTE = "recuperacao_importante"
    EXPECTATIVA_QUEBRADA = "expectativa_quebrada"
    INTERACAO_HUMANA = "interacao_humana"
    REFLEXAO_PERIODICA = "reflexao_periodica"


def _texto(valor: str | None, nome: str, *, opcional: bool = False) -> str | None:
    if valor is None and opcional:
        return None
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"{nome} nao pode ser vazio")
    return valor.strip()


def _utc(valor: str) -> str:
    instante = datetime.fromisoformat(valor)
    if instante.tzinfo is None or instante.utcoffset() is None:
        raise ValueError("timestamp deve possuir timezone")
    return instante.astimezone(timezone.utc).isoformat()

@dataclass(frozen=True)
class DecisaoAtivacaoCognitiva:
    ativar: bool
    motivo: MotivoAtivacaoCognitiva | None
    razao_bloqueio: str | None = None


@dataclass(frozen=True)
class ContextoCognitivo:
    versao_schema: int
    timestamp: str
    motivo_ativacao: MotivoAtivacaoCognitiva
    entidade_principal: str
    estado_tecnico: str
    estado_percepcao: str
    incidente_principal: Mapping[str, Any] | None
    estado_afetivo: Mapping[str, Any]
    emocao_principal: str
    nuances: tuple[str, ...]
    foco_atencao: str | None
    expectativa: Mapping[str, Any] | None
    mudancas_recentes: tuple[Mapping[str, Any], ...]
    dependencias_afetadas: tuple[str, ...]
    truncamentos: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.versao_schema != 1:
            raise ValueError("versao_schema deve ser 1")
        object.__setattr__(self, "timestamp", _utc(self.timestamp))
        object.__setattr__(self, "entidade_principal", _texto(self.entidade_principal, "entidade_principal"))
        object.__setattr__(self, "estado_tecnico", _texto(self.estado_tecnico, "estado_tecnico"))
        object.__setattr__(self, "estado_percepcao", _texto(self.estado_percepcao, "estado_percepcao"))
        object.__setattr__(self, "emocao_principal", _texto(self.emocao_principal, "emocao_principal"))
        object.__setattr__(self, "foco_atencao", _texto(self.foco_atencao, "foco_atencao", opcional=True))
        object.__setattr__(self, "nuances", tuple(dict.fromkeys(self.nuances)))
        object.__setattr__(self, "dependencias_afetadas", tuple(dict.fromkeys(self.dependencias_afetadas)))
        object.__setattr__(self, "truncamentos", tuple(dict.fromkeys(self.truncamentos)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "versao_schema": self.versao_schema,
            "timestamp": self.timestamp,
            "motivo_ativacao": self.motivo_ativacao.value,
            "entidade_principal": self.entidade_principal,
            "estado_tecnico": self.estado_tecnico,
            "estado_percepcao": self.estado_percepcao,
            "incidente_principal": dict(self.incidente_principal) if self.incidente_principal else None,
            "estado_afetivo": dict(self.estado_afetivo),
            "emocao_principal": self.emocao_principal,
            "nuances": list(self.nuances),
            "foco_atencao": self.foco_atencao,
            "expectativa": dict(self.expectativa) if self.expectativa else None,
            "mudancas_recentes": [dict(item) for item in self.mudancas_recentes],
            "dependencias_afetadas": list(self.dependencias_afetadas),
            "truncamentos": list(self.truncamentos),
        }

    def payload_bytes(self) -> int:
        return len(json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
