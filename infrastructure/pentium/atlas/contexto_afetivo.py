from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime

from .modelo_contexto_afetivo import (
    EntidadeAfetiva,
    EstadoExpectativa,
    Expectativa,
    ExperienciaOperacional,
    TipoEntidadeAfetiva,
    TipoExperienciaOperacional,
    VinculoAfetivo,
)


class ContextoAfetivo:
    def __init__(self, capacidade_historico: int):
        if not isinstance(capacidade_historico, int) or capacidade_historico <= 0:
            raise ValueError("capacidade_historico deve ser inteiro > 0")
        self._capacidade = capacidade_historico
        self._entidades: dict[str, EntidadeAfetiva] = {}
        self._vinculos: dict[str, VinculoAfetivo] = {}
        self._expectativas: dict[str, Expectativa] = {}
        self._historico: dict[str, deque[ExperienciaOperacional]] = defaultdict(
            lambda: deque(maxlen=self._capacidade)
        )
        self._experiencia_ids: set[str] = set()

    @property
    def capacidade_historico(self) -> int:
        return self._capacidade

    def entidades(self) -> tuple[EntidadeAfetiva, ...]:
        return tuple(self._entidades[chave] for chave in sorted(self._entidades))

    def vinculos(self) -> tuple[VinculoAfetivo, ...]:
        return tuple(self._vinculos[chave] for chave in sorted(self._vinculos))

    def expectativas(self) -> tuple[Expectativa, ...]:
        return tuple(self._expectativas[chave] for chave in sorted(self._expectativas))

    def cadastrar_entidade(self, entidade: EntidadeAfetiva) -> None:
        atual = self._entidades.get(entidade.entidade_id)
        if atual is not None and atual != entidade:
            raise ValueError(f"entidade_id duplicado: {entidade.entidade_id}")
        self._entidades[entidade.entidade_id] = entidade

    def incorporar_membro(self, entidade_id: str) -> EntidadeAfetiva:
        entidade = self._obter_entidade(entidade_id)
        if entidade.tipo is not TipoEntidadeAfetiva.MEMBRO:
            raise ValueError("somente MEMBRO pode ser incorporado explicitamente")
        if entidade.incorporada:
            return entidade
        entidade = entidade.incorporar()
        self._entidades[entidade_id] = entidade
        return entidade

    def definir_vinculo(self, vinculo: VinculoAfetivo) -> None:
        self._obter_entidade(vinculo.entidade_id)
        self._vinculos[vinculo.entidade_id] = vinculo

    def vinculo_efetivo(self, entidade_id: str) -> VinculoAfetivo | None:
        entidade = self._obter_entidade(entidade_id)
        if entidade.tipo is TipoEntidadeAfetiva.MEMBRO and not entidade.incorporada:
            return None
        return self._vinculos.get(entidade_id)

    def evoluir_vinculo(
        self,
        entidade_id: str,
        delta_familiaridade: float,
        delta_confianca_operacional: float,
    ) -> VinculoAfetivo:
        vinculo = self._vinculos.get(entidade_id)
        if vinculo is None:
            raise KeyError(f"vinculo inexistente: {entidade_id}")
        novo = vinculo.evoluir_experiencia(
            delta_familiaridade,
            delta_confianca_operacional,
        )
        self._vinculos[entidade_id] = novo
        return novo

    def adicionar_expectativa(self, expectativa: Expectativa) -> None:
        self._obter_entidade(expectativa.entidade_id)
        atual = self._expectativas.get(expectativa.expectativa_id)
        if atual is not None and atual != expectativa:
            raise ValueError(f"expectativa_id duplicado: {expectativa.expectativa_id}")
        self._expectativas[expectativa.expectativa_id] = expectativa

    def estado_expectativa(self, expectativa_id: str, agora: str) -> EstadoExpectativa:
        return self._obter_expectativa(expectativa_id).estado_em(agora)

    def concluir_expectativa(self, expectativa_id: str) -> Expectativa:
        expectativa = self._obter_expectativa(expectativa_id).concluir()
        self._expectativas[expectativa_id] = expectativa
        return expectativa

    def cancelar_expectativa(self, expectativa_id: str) -> Expectativa:
        expectativa = self._obter_expectativa(expectativa_id).cancelar()
        self._expectativas[expectativa_id] = expectativa
        return expectativa

    def registrar_experiencia(self, experiencia: ExperienciaOperacional) -> bool:
        self._obter_entidade(experiencia.entidade_id)
        if experiencia.experiencia_id in self._experiencia_ids:
            return False
        fila = self._historico[experiencia.entidade_id]
        if len(fila) == self._capacidade:
            removida = fila[0]
            self._experiencia_ids.discard(removida.experiencia_id)
        fila.append(experiencia)
        self._experiencia_ids.add(experiencia.experiencia_id)
        return True

    def historico_de(self, entidade_id: str) -> tuple[ExperienciaOperacional, ...]:
        self._obter_entidade(entidade_id)
        return tuple(self._historico.get(entidade_id, ()))

    def fator_reincidencia(
        self,
        entidade_id: str,
        agora: str,
        *,
        janela_s: float,
        limite_repeticoes: int,
    ) -> float:
        if janela_s <= 0:
            raise ValueError("janela_s deve ser > 0")
        if not isinstance(limite_repeticoes, int) or limite_repeticoes <= 0:
            raise ValueError("limite_repeticoes deve ser inteiro > 0")
        instante_agora = datetime.fromisoformat(agora)
        if instante_agora.tzinfo is None or instante_agora.utcoffset() is None:
            raise ValueError("agora deve possuir timezone")
        quantidade = 0
        for experiencia in self.historico_de(entidade_id):
            if experiencia.tipo is not TipoExperienciaOperacional.INCIDENTE:
                continue
            ocorrido = datetime.fromisoformat(experiencia.ocorrido_em)
            idade = (instante_agora - ocorrido).total_seconds()
            if 0 <= idade <= janela_s:
                quantidade += 1
        repeticoes = max(0, quantidade - 1)
        return min(1.0, repeticoes / limite_repeticoes)

    def _obter_entidade(self, entidade_id: str) -> EntidadeAfetiva:
        try:
            return self._entidades[entidade_id]
        except KeyError as exc:
            raise KeyError(f"entidade inexistente: {entidade_id}") from exc

    def _obter_expectativa(self, expectativa_id: str) -> Expectativa:
        try:
            return self._expectativas[expectativa_id]
        except KeyError as exc:
            raise KeyError(f"expectativa inexistente: {expectativa_id}") from exc
