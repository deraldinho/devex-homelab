from __future__ import annotations

from dataclasses import replace
from typing import Callable, Mapping

from .grafo_dependencias import GrafoDependencias
from .modelo_incidente import EstadoRecuperacaoIncidente, IncidenteTecnico
from .modelo_percepcao import EstadoObservacao, EstadoPercepcao


class CorrelacionadorIncidentes:
    def __init__(
        self,
        grafo: GrafoDependencias,
        *,
        capacidade_incidentes: int,
        max_entidades_por_incidente: int,
        id_factory: Callable[[], str],
    ):
        if capacidade_incidentes <= 0 or max_entidades_por_incidente <= 0:
            raise ValueError("capacidades devem ser > 0")
        self._grafo = grafo
        self._capacidade = capacidade_incidentes
        self._max_entidades = max_entidades_por_incidente
        self._id_factory = id_factory
        self._ativos: dict[str, IncidenteTecnico] = {}

    def atualizar(self, percepcoes: Mapping[str, EstadoPercepcao], agora: str) -> tuple[IncidenteTecnico, ...]:
        inacessiveis = {
            entidade
            for entidade, estado in percepcoes.items()
            if estado.estado is EstadoObservacao.INACESSIVEL
        }
        resultados: list[IncidenteTecnico] = []
        for root, incidente in list(self._ativos.items()):
            if root not in inacessiveis:
                encerrado = replace(
                    incidente,
                    estado_recuperacao=EstadoRecuperacaoIncidente.RECUPERADO,
                    recuperado_em=agora,
                )
                resultados.append(encerrado)
                del self._ativos[root]

        roots = self._selecionar_roots(inacessiveis)
        for root in roots:
            afetadas = {root}
            afetadas.update(set(self._grafo.dependentes_transitivos(root)) & inacessiveis)
            materializadas = tuple(sorted(afetadas))[: self._max_entidades]
            incidente = self._ativos.get(root)
            if incidente is None:
                if len(self._ativos) >= self._capacidade:
                    raise OverflowError("capacidade de incidentes excedida")
                incidente = IncidenteTecnico(
                    incidente_id=self._id_factory(),
                    entidade_principal=root,
                    tipo="indisponibilidade_correlacionada",
                    gravidade="critical",
                    inicio_em=agora,
                    causa_provavel=root,
                    confianca_causal=len(afetadas) / max(1, len(inacessiveis)),
                    entidades_afetadas=materializadas,
                    total_entidades_afetadas=len(afetadas),
                )
            else:
                incidente = replace(
                    incidente,
                    confianca_causal=len(afetadas) / max(1, len(inacessiveis)),
                    entidades_afetadas=materializadas,
                    total_entidades_afetadas=len(afetadas),
                )
            self._ativos[root] = incidente
            resultados.append(incidente)
        return tuple(sorted(resultados, key=lambda item: (item.estado_recuperacao.value, item.entidade_principal)))

    def _selecionar_roots(self, inacessiveis: set[str]) -> tuple[str, ...]:
        if not inacessiveis:
            return ()
        coberturas = {
            entidade: 1 + len(set(self._grafo.dependentes_transitivos(entidade)) & inacessiveis)
            for entidade in inacessiveis
        }
        ordenados = sorted(inacessiveis, key=lambda entidade: (-coberturas[entidade], entidade))
        cobertos: set[str] = set()
        roots: list[str] = []
        for entidade in ordenados:
            if entidade in cobertos:
                continue
            roots.append(entidade)
            cobertos.add(entidade)
            cobertos.update(set(self._grafo.dependentes_transitivos(entidade)) & inacessiveis)
        return tuple(roots)

    def incidentes_ativos(self) -> tuple[IncidenteTecnico, ...]:
        return tuple(self._ativos[chave] for chave in sorted(self._ativos))

    def restaurar_ativos(self, incidentes) -> None:
        restaurados = tuple(incidentes)
        if len(restaurados) > self._capacidade:
            raise OverflowError("incidentes restaurados excedem capacidade")
        ativos: dict[str, IncidenteTecnico] = {}
        for incidente in restaurados:
            if incidente.estado_recuperacao is not EstadoRecuperacaoIncidente.ABERTO:
                continue
            if incidente.entidade_principal in ativos:
                raise ValueError("entidade principal possui incidente ativo duplicado")
            ativos[incidente.entidade_principal] = incidente
        self._ativos = ativos
