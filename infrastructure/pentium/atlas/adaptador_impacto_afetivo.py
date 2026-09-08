from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .emocao_derivada import ContextoEmocional
from .modelo_afetivo import ImpulsoAfetivo
from .modelo_contexto_afetivo import VinculoAfetivo
from .modelo_foco import AssuntoFoco
from .modelo_incidente import EstadoRecuperacaoIncidente, IncidenteTecnico
from .modelo_percepcao import EstadoObservacao
from .pipeline_percepcao_correlacao import ResultadoPipelinePercepcaoCorrelacao
from .stimulus_model import Stimulus, StimulusSeverity


def _b01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@dataclass(frozen=True)
class ConfigImpactoAfetivo:
    gravidades: Mapping[str, float]
    gravidade_fallback: float
    peso_operacional_minimo: float
    limiar_critico: float
    ganho_estresse_incidente: float
    ganho_ativacao_incidente: float
    perda_valencia_incidente: float
    ganho_ativacao_insegura: float
    ganho_curiosidade_insegura: float
    reducao_estresse_recuperacao: float
    ganho_valencia_recuperacao: float
    ganho_confianca_recuperacao: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "gravidades", {str(k): _b01(v) for k, v in self.gravidades.items()})
        for nome in (
            "gravidade_fallback", "peso_operacional_minimo", "limiar_critico",
            "ganho_estresse_incidente", "ganho_ativacao_incidente", "perda_valencia_incidente",
            "ganho_ativacao_insegura", "ganho_curiosidade_insegura",
            "reducao_estresse_recuperacao", "ganho_valencia_recuperacao", "ganho_confianca_recuperacao",
        ):
            object.__setattr__(self, nome, _b01(getattr(self, nome)))


@dataclass(frozen=True)
class ImpactoAfetivoObservacional:
    impulso: ImpulsoAfetivo
    assunto: AssuntoFoco
    contexto_emocional: ContextoEmocional
    incidente_id: str | None
    entidade_id: str


class AdaptadorImpactoAfetivo:
    def __init__(self, config: ConfigImpactoAfetivo):
        self._config = config

    def _peso_vinculo(self, vinculo: VinculoAfetivo | None) -> float:
        if vinculo is None:
            return self._config.peso_operacional_minimo
        peso = (vinculo.importancia + vinculo.responsabilidade + vinculo.dependencia_operacional) / 3.0
        return max(self._config.peso_operacional_minimo, _b01(peso))
    def _incidente_relevante(
        self,
        resultado: ResultadoPipelinePercepcaoCorrelacao,
    ) -> IncidenteTecnico | None:
        entidade = resultado.percepcao.entidade_id
        candidatos = [
            incidente for incidente in resultado.incidentes
            if entidade == incidente.entidade_principal or entidade in incidente.entidades_afetadas
        ]
        if not candidatos:
            return None
        recuperados = [
            item for item in candidatos
            if item.estado_recuperacao is EstadoRecuperacaoIncidente.RECUPERADO
        ]
        return sorted(recuperados or candidatos, key=lambda item: item.incidente_id)[0]

    def _urgencia(self, severity: StimulusSeverity) -> float:
        return {
            StimulusSeverity.INFO: 0.2,
            StimulusSeverity.NOTICE: 0.35,
            StimulusSeverity.WARNING: 0.6,
            StimulusSeverity.CRITICAL: 1.0,
        }[severity]

    def derivar(
        self,
        stimulus: Stimulus,
        resultado: ResultadoPipelinePercepcaoCorrelacao,
        vinculo: VinculoAfetivo | None,
        reincidencia: float,
    ) -> ImpactoAfetivoObservacional:
        percepcao = resultado.percepcao
        incidente = self._incidente_relevante(resultado)
        peso = self._peso_vinculo(vinculo)
        gravidade = 0.0
        critico = False
        recuperado = False
        if incidente is not None:
            gravidade = self._config.gravidades.get(
                incidente.gravidade,
                self._config.gravidade_fallback,
            )
            recuperado = incidente.estado_recuperacao is EstadoRecuperacaoIncidente.RECUPERADO
            critico = gravidade >= self._config.limiar_critico and not recuperado
            confianca = _b01(incidente.confianca_causal)
            forca = _b01(gravidade * peso * confianca)
            if recuperado:
                impulso = ImpulsoAfetivo(
                    motivo=f"recuperacao:{incidente.incidente_id}",
                    delta_valencia=self._config.ganho_valencia_recuperacao * forca,
                    delta_estresse=-self._config.reducao_estresse_recuperacao * forca,
                    delta_confianca=self._config.ganho_confianca_recuperacao * forca,
                )
            else:
                impulso = ImpulsoAfetivo(
                    motivo=f"incidente:{incidente.incidente_id}",
                    delta_valencia=-self._config.perda_valencia_incidente * forca,
                    delta_ativacao=self._config.ganho_ativacao_incidente * forca,
                    delta_estresse=self._config.ganho_estresse_incidente * forca,
                )
            assunto_id = incidente.incidente_id
            impacto = forca
        else:
            insegura = percepcao.estado in {
                EstadoObservacao.PARCIALMENTE_OBSERVADO,
                EstadoObservacao.INACESSIVEL,
                EstadoObservacao.DESCONHECIDO,
            } or percepcao.conflito_evidencias
            incerteza = _b01(1.0 - percepcao.confianca) if insegura else 0.0
            forca = _b01(max(0.1, incerteza) * peso) if insegura else 0.0
            impulso = ImpulsoAfetivo(
                motivo=f"observacao:{percepcao.entidade_id}",
                delta_ativacao=self._config.ganho_ativacao_insegura * forca,
                delta_curiosidade=self._config.ganho_curiosidade_insegura * forca,
            )
            assunto_id = f"observacao:{percepcao.entidade_id}"
            impacto = forca
        contexto = ContextoEmocional(
            reincidencia=_b01(reincidencia),
            criticidade_relevante=critico,
            recuperacao_relevante=recuperado,
            percepcao_insegura=(
                percepcao.estado is not EstadoObservacao.OBSERVADO
                or percepcao.conflito_evidencias
            ),
        )
        assunto = AssuntoFoco(
            assunto_id=assunto_id,
            entidade_id=percepcao.entidade_id,
            gravidade=gravidade,
            impacto_afetivo=impacto,
            importancia=vinculo.importancia if vinculo is not None else self._config.peso_operacional_minimo,
            novidade=stimulus.novelty,
            urgencia=self._urgencia(stimulus.severity),
            recencia=1.0,
            critico=critico,
            recuperado=recuperado,
        )
        return ImpactoAfetivoObservacional(
            impulso=impulso,
            assunto=assunto,
            contexto_emocional=contexto,
            incidente_id=incidente.incidente_id if incidente is not None else None,
            entidade_id=percepcao.entidade_id,
        )
