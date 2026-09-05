from __future__ import annotations

from dataclasses import dataclass

from .modelo_percepcao import EvidenciaPercepcao, ResultadoEvidencia
from .stimulus_model import Stimulus


@dataclass(frozen=True)
class ConfigFontePercepcao:
    source: str
    entidade_id: str
    campos_alcance: tuple[str, ...]
    confianca: float

    def __post_init__(self) -> None:
        if not self.source or not self.entidade_id:
            raise ValueError("source e entidade_id sao obrigatorios")
        object.__setattr__(self, "campos_alcance", tuple(self.campos_alcance))
        object.__setattr__(self, "confianca", max(0.0, min(1.0, float(self.confianca))))


def evidencia_de_stimulus(stimulus: Stimulus, config: ConfigFontePercepcao) -> EvidenciaPercepcao:
    if stimulus.source != config.source:
        raise ValueError(f"stimulus source inesperado: {stimulus.source}")
    payload = dict(stimulus.payload)
    conclusiva = False
    if stimulus.kind == "source_error":
        resultado = ResultadoEvidencia.FONTE_INDISPONIVEL
    else:
        valores = [payload[campo] for campo in config.campos_alcance if campo in payload]
        if valores:
            resultado = ResultadoEvidencia.DISPONIVEL if any(bool(valor) for valor in valores) else ResultadoEvidencia.INDISPONIVEL
        else:
            resultado = ResultadoEvidencia.DISPONIVEL
    return EvidenciaPercepcao(
        stimulus.stimulus_id,
        config.entidade_id,
        stimulus.source,
        resultado,
        config.confianca,
        stimulus.timestamp,
        conclusiva,
    )
