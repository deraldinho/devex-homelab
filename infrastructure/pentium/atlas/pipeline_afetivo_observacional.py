from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass
import json
from pathlib import Path

from .adaptador_impacto_afetivo import ConfigImpactoAfetivo
from .modelo_contexto_afetivo import ExperienciaOperacional, TipoExperienciaOperacional
from .modelo_incidente import EstadoRecuperacaoIncidente
from .stimulus_model import Stimulus


@dataclass(frozen=True)
class ConfigPipelineAfetivoObservacional:
    capacidade_stimulus_ids: int
    capacidade_incidentes: int
    capacidade_assuntos: int
    capacidade_erros: int
    janela_reincidencia_s: float
    limite_repeticoes: int
    impacto: ConfigImpactoAfetivo


def carregar_config_observation_affective(path: Path) -> ConfigPipelineAfetivoObservacional:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("observation affective config schema_version must be 1")
    capacidades = payload.get("capacidades")
    ganhos = payload.get("ganhos")
    gravidades = payload.get("gravidades")
    if not isinstance(capacidades, dict) or not isinstance(ganhos, dict) or not isinstance(gravidades, dict):
        raise ValueError("observation affective config sections are required")
    valores_capacidade = {
        nome: int(capacidades[nome])
        for nome in ("stimulus_ids", "incidentes", "assuntos", "erros")
    }
    if any(valor <= 0 for valor in valores_capacidade.values()):
        raise ValueError("observation affective capacities must be > 0")
    impacto = ConfigImpactoAfetivo(
        gravidades=gravidades,
        gravidade_fallback=payload["gravidade_fallback"],
        peso_operacional_minimo=payload["peso_operacional_minimo"],
        limiar_critico=payload["limiar_critico"],
        ganho_estresse_incidente=ganhos["estresse_incidente"],
        ganho_ativacao_incidente=ganhos["ativacao_incidente"],
        perda_valencia_incidente=ganhos["perda_valencia_incidente"],
        ganho_ativacao_insegura=ganhos["ativacao_insegura"],
        ganho_curiosidade_insegura=ganhos["curiosidade_insegura"],
        reducao_estresse_recuperacao=ganhos["reducao_estresse_recuperacao"],
        ganho_valencia_recuperacao=ganhos["valencia_recuperacao"],
        ganho_confianca_recuperacao=ganhos["confianca_recuperacao"],
    )
    janela = float(payload["janela_reincidencia_s"])
    limite = int(payload["limite_repeticoes"])
    if janela <= 0 or limite <= 0:
        raise ValueError("reincidence policy must be > 0")
    return ConfigPipelineAfetivoObservacional(
        valores_capacidade["stimulus_ids"],
        valores_capacidade["incidentes"],
        valores_capacidade["assuntos"],
        valores_capacidade["erros"],
        janela,
        limite,
        impacto,
    )


@dataclass(frozen=True)
class ResultadoPipelineAfetivoObservacional:
    aceito: bool
    resultado_foco_emocao: object | None = None
    impacto: object | None = None


class PipelineAfetivoObservacional:
    def __init__(
        self,
        *,
        pipeline_percepcao,
        contexto_afetivo,
        adaptador,
        motor_afetivo,
        contexto_foco_emocao,
        affective_runtime,
        capacidade_stimulus_ids: int,
        capacidade_incidentes: int,
        capacidade_assuntos: int,
        capacidade_erros: int,
        janela_reincidencia_s: float,
        limite_repeticoes: int,
    ):
        for valor in (capacidade_stimulus_ids, capacidade_incidentes, capacidade_assuntos, capacidade_erros, limite_repeticoes):
            if not isinstance(valor, int) or valor <= 0:
                raise ValueError("capacidades e limite_repeticoes devem ser inteiros > 0")
        if janela_reincidencia_s <= 0:
            raise ValueError("janela_reincidencia_s deve ser > 0")
        self._pipeline_percepcao = pipeline_percepcao
        self._contexto_afetivo = contexto_afetivo
        self._adaptador = adaptador
        self._motor_afetivo = motor_afetivo
        self._contexto_foco_emocao = contexto_foco_emocao
        self._affective_runtime = affective_runtime
        self._capacidade_stimulus_ids = capacidade_stimulus_ids
        self._stimulus_order = deque()
        self._stimulus_ids: set[str] = set()
        self._incidentes = OrderedDict()
        self._capacidade_incidentes = capacidade_incidentes
        self._assuntos = OrderedDict()
        self._capacidade_assuntos = capacidade_assuntos
        self._erros = deque(maxlen=capacidade_erros)
        self._janela_reincidencia_s = float(janela_reincidencia_s)
        self._limite_repeticoes = limite_repeticoes

    def errors(self) -> tuple[str, ...]:
        return tuple(self._erros)

    def _erro(self, prefixo: str, exc: Exception) -> None:
        self._erros.append(f"{prefixo}:{type(exc).__name__}")

    def _lembrar_stimulus(self, stimulus_id: str) -> bool:
        if stimulus_id in self._stimulus_ids:
            return False
        if len(self._stimulus_order) >= self._capacidade_stimulus_ids:
            antigo = self._stimulus_order.popleft()
            self._stimulus_ids.discard(antigo)
        self._stimulus_order.append(stimulus_id)
        self._stimulus_ids.add(stimulus_id)
        return True

    def _atualizar_assunto(self, assunto) -> tuple:
        self._assuntos[assunto.assunto_id] = assunto
        self._assuntos.move_to_end(assunto.assunto_id)
        while len(self._assuntos) > self._capacidade_assuntos:
            self._assuntos.popitem(last=False)
        return tuple(self._assuntos[chave] for chave in sorted(self._assuntos))
    def _contexto_a2(self, entidade_id: str, agora: str):
        vinculo = None
        reincidencia = 0.0
        try:
            vinculo = self._contexto_afetivo.vinculo_efetivo(entidade_id)
            reincidencia = self._contexto_afetivo.fator_reincidencia(
                entidade_id,
                agora,
                janela_s=self._janela_reincidencia_s,
                limite_repeticoes=self._limite_repeticoes,
            )
        except Exception as exc:
            self._erro("contexto_afetivo", exc)
        return vinculo, reincidencia

    def _registrar_transicao_incidente(self, impacto, resultado, agora: str) -> None:
        if impacto.incidente_id is None:
            return
        incidente = next(
            (item for item in resultado.incidentes if item.incidente_id == impacto.incidente_id),
            None,
        )
        if incidente is None:
            return
        estado = incidente.estado_recuperacao
        anterior = self._incidentes.get(incidente.incidente_id)
        if anterior is estado:
            return
        self._incidentes[incidente.incidente_id] = estado
        self._incidentes.move_to_end(incidente.incidente_id)
        while len(self._incidentes) > self._capacidade_incidentes:
            self._incidentes.popitem(last=False)
        tipo = (
            TipoExperienciaOperacional.RECUPERACAO
            if estado is EstadoRecuperacaoIncidente.RECUPERADO
            else TipoExperienciaOperacional.INCIDENTE
        )
        experiencia = ExperienciaOperacional(
            f"{incidente.incidente_id}:{estado.value}",
            incidente.entidade_principal,
            tipo,
            agora,
        )
        try:
            self._contexto_afetivo.registrar_experiencia(experiencia)
        except Exception as exc:
            self._erro("contexto_afetivo", exc)
    def processar(self, stimulus: Stimulus) -> ResultadoPipelineAfetivoObservacional:
        if not self._lembrar_stimulus(stimulus.stimulus_id):
            return ResultadoPipelineAfetivoObservacional(False)

        resultado = self._pipeline_percepcao.processar(stimulus)
        vinculo, reincidencia = self._contexto_a2(
            resultado.percepcao.entidade_id,
            stimulus.timestamp,
        )
        impacto = self._adaptador.derivar(
            stimulus,
            resultado,
            vinculo,
            reincidencia,
        )
        self._registrar_transicao_incidente(
            impacto,
            resultado,
            stimulus.timestamp,
        )
        estado = self._motor_afetivo.aplicar_impulso(
            impacto.impulso,
            ocorrido_em=stimulus.timestamp,
        )
        assuntos = self._atualizar_assunto(impacto.assunto)
        resultado_foco = self._contexto_foco_emocao.processar(
            estado,
            assuntos,
            impacto.contexto_emocional,
            stimulus.timestamp,
        )
        self._affective_runtime.atualizar_resultado(
            resultado_foco,
            reacao_critica=impacto.contexto_emocional.criticidade_relevante,
        )
        return ResultadoPipelineAfetivoObservacional(
            True,
            resultado_foco,
            impacto,
        )
