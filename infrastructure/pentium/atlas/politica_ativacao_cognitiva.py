from __future__ import annotations

from collections import OrderedDict, deque
from datetime import datetime, timezone

from .configuracao_cognitiva import PoliticaAtivacaoCognitiva
from .modelo_contexto_cognitivo import DecisaoAtivacaoCognitiva, MotivoAtivacaoCognitiva


def _instante(valor: str) -> datetime:
    instante = datetime.fromisoformat(valor)
    if instante.tzinfo is None or instante.utcoffset() is None:
        raise ValueError("agora deve possuir timezone")
    return instante.astimezone(timezone.utc)


class ActivationPolicy:
    def __init__(self, politica: PoliticaAtivacaoCognitiva):
        self._politica = politica
        self._autonomas: deque[datetime] = deque(maxlen=max(8, politica.max_ativacoes_autonomas_janela * 4))
        self._fingerprints: OrderedDict[str, datetime] = OrderedDict()
        self._max_fingerprints = max(16, politica.max_ativacoes_autonomas_janela * 8)

    def _limpar(self, agora: datetime) -> None:
        janela = self._politica.janela_orcamento_s
        while self._autonomas and (agora - self._autonomas[0]).total_seconds() > janela:
            self._autonomas.popleft()
        expirados = [fp for fp, instante in self._fingerprints.items() if (agora - instante).total_seconds() > janela]
        for fp in expirados:
            self._fingerprints.pop(fp, None)

    def registrar_ativacao(self, fingerprint: str, agora: str, autonomo: bool) -> None:
        instante = _instante(agora)
        self._limpar(instante)
        if autonomo:
            self._autonomas.append(instante)
            self._fingerprints[fingerprint] = instante
            self._fingerprints.move_to_end(fingerprint)
            while len(self._fingerprints) > self._max_fingerprints:
                self._fingerprints.popitem(last=False)

    def avaliar(self, *, fingerprint: str, agora: str, interacao_humana: bool = False,
                criticidade: bool = False, expectativa_quebrada: bool = False,
                recuperacao_importante: bool = False, mudanca_estado: bool = False,
                delta_afetivo: float = 0.0, novidade: float = 0.0,
                reflexao_periodica: bool = False) -> DecisaoAtivacaoCognitiva:
        instante = _instante(agora)
        self._limpar(instante)

        if interacao_humana:
            return DecisaoAtivacaoCognitiva(True, MotivoAtivacaoCognitiva.INTERACAO_HUMANA)

        motivo = None
        if criticidade:
            motivo = MotivoAtivacaoCognitiva.CRITICIDADE_TECNICA
        elif expectativa_quebrada:
            motivo = MotivoAtivacaoCognitiva.EXPECTATIVA_QUEBRADA
        elif recuperacao_importante:
            motivo = MotivoAtivacaoCognitiva.RECUPERACAO_IMPORTANTE
        elif mudanca_estado:
            motivo = MotivoAtivacaoCognitiva.MUDANCA_ESTADO
        elif delta_afetivo >= self._politica.delta_afetivo_minimo:
            motivo = MotivoAtivacaoCognitiva.MUDANCA_AFETIVA
        elif novidade >= self._politica.novidade_minima:
            motivo = MotivoAtivacaoCognitiva.NOVIDADE_RELEVANTE
        elif reflexao_periodica:
            motivo = MotivoAtivacaoCognitiva.REFLEXAO_PERIODICA
        else:
            return DecisaoAtivacaoCognitiva(False, None, "sem_motivo")

        anterior = self._fingerprints.get(fingerprint)
        if anterior is not None and (instante - anterior).total_seconds() < self._politica.cooldown_s:
            return DecisaoAtivacaoCognitiva(False, None, "cooldown")
        if len(self._autonomas) >= self._politica.max_ativacoes_autonomas_janela:
            return DecisaoAtivacaoCognitiva(False, None, "orcamento")
        return DecisaoAtivacaoCognitiva(True, motivo)
