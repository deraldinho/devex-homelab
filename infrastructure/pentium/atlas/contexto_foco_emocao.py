from __future__ import annotations

from dataclasses import dataclass, replace

from .emocao_derivada import ContextoEmocional, EmocaoDerivada, ROTULOS_EMOCAO, derivar_emocao
from .modelo_afetivo import EstadoAfetivo
from .modelo_foco import AssuntoFoco, FocoAtencao, PoliticaFoco
from .motor_foco import MotorFoco


@dataclass(frozen=True)
class ResultadoFocoEmocao:
    estado_afetivo: EstadoAfetivo
    foco: FocoAtencao
    emocao: EmocaoDerivada
    rotulos_canonicos: tuple[str, ...] = ROTULOS_EMOCAO


class ContextoFocoEmocao:
    def __init__(self, politica_foco: PoliticaFoco, capacidade_nuances: int = 2):
        if not isinstance(capacidade_nuances, int) or capacidade_nuances < 0:
            raise ValueError("capacidade_nuances deve ser inteiro >= 0")
        self._motor_foco = MotorFoco(politica_foco)
        self._capacidade_nuances = capacidade_nuances

    def processar(
        self,
        estado: EstadoAfetivo,
        assuntos: tuple[AssuntoFoco, ...],
        contexto_emocional: ContextoEmocional,
        agora: str,
    ) -> ResultadoFocoEmocao:
        foco = self._motor_foco.atualizar(assuntos, agora)
        foco_id = foco.principal.assunto_id if foco.principal else None
        estado_com_foco = replace(estado, foco_atencao=foco_id)
        emocao = derivar_emocao(
            estado_com_foco,
            contexto_emocional,
            capacidade_nuances=self._capacidade_nuances,
        )
        return ResultadoFocoEmocao(
            estado_afetivo=estado_com_foco,
            foco=foco,
            emocao=emocao,
        )
