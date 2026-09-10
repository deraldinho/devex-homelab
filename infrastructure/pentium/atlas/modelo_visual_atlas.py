from __future__ import annotations
import math
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum

class ModoVisual(str, Enum):
    OCIOSO = "OCIOSO"
    OBSERVANDO = "OBSERVANDO"
    CONVERSANDO = "CONVERSANDO"
    REAGINDO = "REAGINDO"

class ExpressaoVisual(str, Enum):
    SERENO = "SERENO"
    ENGAJADO = "ENGAJADO"
    CURIOSO = "CURIOSO"
    ATENTO = "ATENTO"
    PREOCUPADO = "PREOCUPADO"
    SOB_PRESSAO = "SOB_PRESSAO"
    RECUPERANDO = "RECUPERANDO"

def _enum(valor, tipo):
    try:
        return valor if isinstance(valor, tipo) else tipo(str(valor))
    except ValueError as exc:
        raise ValueError(f"{tipo.__name__} invalido") from exc

def _limit01(valor, nome):
    numero = float(valor)
    if not math.isfinite(numero):
        raise ValueError(f"{nome} deve ser finito")
    return max(0.0, min(1.0, numero))

def _utc(valor):
    instante = datetime.fromisoformat(valor)
    if instante.tzinfo is None or instante.utcoffset() is None:
        raise ValueError("atualizado_em deve possuir timezone")
    return instante.astimezone(timezone.utc).isoformat()

@dataclass(frozen=True)
class EstadoInteracaoVisual:
    ouvindo: bool = False
    pensando: bool = False
    falando: bool = False
    duvida_identidade: bool = False
    degradado: bool = False
    atualizado_em: str = "1970-01-01T00:00:00+00:00"
    def __post_init__(self):
        object.__setattr__(self, "atualizado_em", _utc(self.atualizado_em))

@dataclass(frozen=True)
class EstadoVisualAtlas:
    modo: ModoVisual | str
    expressao: ExpressaoVisual | str
    intensidade_expressao: float
    foco_visual: str
    direcao_olhar: str
    gesto_atual: str
    velocidade_movimento: float
    intensidade_movimento: float
    falando: bool
    ouvindo: bool
    pensando: bool
    duvida_identidade: bool
    transicao_ms: int
    versao_avatar: int = 1
    postura_atual: str = "NEUTRO"
    lado_gesto: str = "none"
    alvo_locomocao: str = "auto"
    acao_pet: str = "PATROL"

    def __post_init__(self):
        object.__setattr__(self, "modo", _enum(self.modo, ModoVisual))
        object.__setattr__(self, "expressao", _enum(self.expressao, ExpressaoVisual))
        object.__setattr__(self, "intensidade_expressao", _limit01(self.intensidade_expressao, "intensidade_expressao"))
        object.__setattr__(self, "velocidade_movimento", _limit01(self.velocidade_movimento, "velocidade_movimento"))
        object.__setattr__(self, "intensidade_movimento", _limit01(self.intensidade_movimento, "intensidade_movimento"))
        if not 120 <= int(self.transicao_ms) <= 1500:
            raise ValueError("transicao_ms fora do bound")
        object.__setattr__(self, "transicao_ms", int(self.transicao_ms))
        object.__setattr__(self, "foco_visual", str(self.foco_visual).strip() or "neutro")

    def para_dict(self):
        data = asdict(self)
        data["modo"] = self.modo.value
        data["expressao"] = self.expressao.value
        return data
