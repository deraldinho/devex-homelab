from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Callable, Mapping

from .adaptador_stimulus_percepcao import ConfigFontePercepcao, evidencia_de_stimulus
from .correlacionador_incidentes import CorrelacionadorIncidentes
from .grafo_dependencias import GrafoDependencias
from .modelo_incidente import IncidenteTecnico
from .modelo_percepcao import EstadoPercepcao, EvidenciaPercepcao
from .percepcao import PoliticaConfirmacaoPercepcao, consolidar_percepcao
from .stimulus_model import Stimulus


@dataclass(frozen=True)
class ResultadoPipelinePercepcaoCorrelacao:
    aceito: bool
    percepcao: EstadoPercepcao
    incidentes: tuple[IncidenteTecnico, ...]


class PipelinePercepcaoCorrelacao:
    def __init__(
        self,
        configs_fontes: Mapping[str, ConfigFontePercepcao],
        politica: PoliticaConfirmacaoPercepcao,
        grafo: GrafoDependencias,
        *,
        capacidade_evidencias_por_entidade: int,
        capacidade_incidentes: int,
        max_entidades_por_incidente: int,
        id_factory: Callable[[], str],
    ):
        if capacidade_evidencias_por_entidade <= 0:
            raise ValueError("capacidade_evidencias_por_entidade deve ser > 0")
        self._configs = dict(configs_fontes)
        self._politica = politica
        self._capacidade = capacidade_evidencias_por_entidade
        self._evidencias: dict[str, deque[EvidenciaPercepcao]] = defaultdict(lambda: deque(maxlen=self._capacidade))
        self._stimulus_ids: set[str] = set()
        self._percepcoes: dict[str, EstadoPercepcao] = {}
        self._correlacionador = CorrelacionadorIncidentes(
            grafo,
            capacidade_incidentes=capacidade_incidentes,
            max_entidades_por_incidente=max_entidades_por_incidente,
            id_factory=id_factory,
        )

    def restaurar_estado(self, percepcoes, incidentes) -> None:
        restauradas = tuple(percepcoes)
        entidades_validas = {config.entidade_id for config in self._configs.values()}
        por_entidade = {}
        for percepcao in restauradas:
            if percepcao.entidade_id not in entidades_validas:
                raise ValueError(f"entidade restaurada sem configuracao: {percepcao.entidade_id}")
            if percepcao.entidade_id in por_entidade:
                raise ValueError(f"percepcao restaurada duplicada: {percepcao.entidade_id}")
            por_entidade[percepcao.entidade_id] = percepcao
        incidentes_restaurados = tuple(incidentes)
        for incidente in incidentes_restaurados:
            if incidente.entidade_principal not in entidades_validas:
                raise ValueError(f"incidente restaurado sem entidade configurada: {incidente.entidade_principal}")
        self._percepcoes = por_entidade
        self._correlacionador.restaurar_ativos(incidentes_restaurados)

    def processar(self, stimulus: Stimulus) -> ResultadoPipelinePercepcaoCorrelacao:
        config = self._configs.get(stimulus.source)
        if config is None:
            raise KeyError(f"fonte de percepcao nao configurada: {stimulus.source}")
        entidade_id = config.entidade_id
        if stimulus.stimulus_id in self._stimulus_ids:
            percepcao = self._percepcoes.get(entidade_id)
            if percepcao is None:
                raise RuntimeError("stimulus duplicado sem percepcao previa")
            return ResultadoPipelinePercepcaoCorrelacao(
                False,
                percepcao,
                self._correlacionador.incidentes_ativos(),
            )

        evidencia = evidencia_de_stimulus(stimulus, config)
        fila = self._evidencias[entidade_id]
        fila.append(evidencia)
        self._stimulus_ids.add(stimulus.stimulus_id)
        percepcao = consolidar_percepcao(
            entidade_id,
            tuple(fila),
            self._politica,
            stimulus.timestamp,
        )
        self._percepcoes[entidade_id] = percepcao
        incidentes = self._correlacionador.atualizar(self._percepcoes, stimulus.timestamp)
        return ResultadoPipelinePercepcaoCorrelacao(True, percepcao, incidentes)

    def percepcoes(self) -> tuple[EstadoPercepcao, ...]:
        return tuple(self._percepcoes[chave] for chave in sorted(self._percepcoes))

    def evidencias_de(self, entidade_id: str) -> tuple[EvidenciaPercepcao, ...]:
        return tuple(self._evidencias.get(entidade_id, ()))

    def incidentes_ativos(self) -> tuple[IncidenteTecnico, ...]:
        return self._correlacionador.incidentes_ativos()

    def restaurar(self, percepcoes, incidentes) -> None:
        restauradas = tuple(percepcoes)
        if len(restauradas) > len(self._configs):
            raise OverflowError("percepcoes restauradas excedem fontes configuradas")
        conhecidas = {config.entidade_id for config in self._configs.values()}
        if any(item.entidade_id not in conhecidas for item in restauradas):
            raise ValueError("percepcao restaurada possui entidade nao configurada")
        self._percepcoes = {item.entidade_id: item for item in restauradas}
        self._correlacionador.restaurar_ativos(incidentes)
