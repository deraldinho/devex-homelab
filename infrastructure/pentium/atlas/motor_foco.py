from __future__ import annotations

from .modelo_foco import AssuntoFoco, FocoAtencao, PoliticaFoco


class MotorFoco:
    def __init__(self, politica: PoliticaFoco):
        self._politica = politica
        self._foco: FocoAtencao | None = None

    @staticmethod
    def pontuacao(assunto: AssuntoFoco) -> float:
        base = (
            assunto.gravidade
            + assunto.impacto_afetivo
            + assunto.importancia
            + assunto.novidade
            + assunto.urgencia
            + assunto.recencia
        ) / 6.0
        if assunto.recuperado:
            return base
        return base

    def _pontuacao_efetiva(self, assunto: AssuntoFoco) -> float:
        valor = self.pontuacao(assunto)
        if assunto.recuperado:
            valor *= self._politica.fator_recuperacao
        return valor

    def atualizar(self, assuntos: tuple[AssuntoFoco, ...], agora: str) -> FocoAtencao:
        candidatos = {assunto.assunto_id: assunto for assunto in assuntos}
        atual = self._foco.principal if self._foco is not None else None
        if atual is not None and atual.assunto_id not in candidatos:
            candidatos[atual.assunto_id] = atual
        if atual is not None:
            atual = candidatos[atual.assunto_id]

        ordenados = sorted(
            candidatos.values(),
            key=lambda item: (-int(item.critico), -self._pontuacao_efetiva(item), item.assunto_id),
        )

        escolhido = atual
        criticos = [item for item in ordenados if item.critico]
        if criticos:
            escolhido = criticos[0]
        elif escolhido is None and ordenados:
            escolhido = ordenados[0]
        elif ordenados and escolhido is not None:
            melhor = ordenados[0]
            if melhor.assunto_id != escolhido.assunto_id:
                atual_score = self._pontuacao_efetiva(escolhido)
                melhor_score = self._pontuacao_efetiva(melhor)
                if melhor_score > atual_score + self._politica.margem_histerese:
                    escolhido = melhor

        secundarios = tuple(
            item for item in ordenados
            if escolhido is None or item.assunto_id != escolhido.assunto_id
        )[: self._politica.capacidade_secundarios]
        self._foco = FocoAtencao(
            escolhido,
            secundarios,
            agora,
            self._politica.capacidade_secundarios,
        )
        return self._foco
