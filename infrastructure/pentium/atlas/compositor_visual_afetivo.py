from __future__ import annotations

from .contexto_foco_emocao import ResultadoFocoEmocao
from .modelo_visual_atlas import EstadoInteracaoVisual, EstadoVisualAtlas, ExpressaoVisual, ModoVisual

_MAPA = {
    "calmo": ExpressaoVisual.SERENO,
    "confiante": ExpressaoVisual.SERENO,
    "satisfeito": ExpressaoVisual.SERENO,
    "interessado": ExpressaoVisual.ENGAJADO,
    "curioso": ExpressaoVisual.CURIOSO,
    "atento": ExpressaoVisual.ATENTO,
    "vigilante": ExpressaoVisual.ATENTO,
    "preocupado": ExpressaoVisual.PREOCUPADO,
    "estressado": ExpressaoVisual.SOB_PRESSAO,
    "alarmado": ExpressaoVisual.SOB_PRESSAO,
    "frustrado": ExpressaoVisual.SOB_PRESSAO,
    "aliviado": ExpressaoVisual.RECUPERANDO,
}

class CompositorVisualAfetivo:
    def compor(
        self,
        resultado: ResultadoFocoEmocao,
        interacao: EstadoInteracaoVisual,
        *,
        reacao_critica: bool = False,
    ) -> EstadoVisualAtlas:
        expressao = _MAPA[resultado.emocao.principal]
        foco = resultado.foco.principal.entidade_id if resultado.foco.principal else "neutro"
        if interacao.falando or interacao.pensando or interacao.ouvindo:
            modo = ModoVisual.CONVERSANDO
        elif reacao_critica:
            modo = ModoVisual.REAGINDO
        elif resultado.foco.principal is not None:
            modo = ModoVisual.OBSERVANDO
        else:
            modo = ModoVisual.OCIOSO

        gesto = "nenhum"
        if interacao.duvida_identidade:
            gesto = "duvida"
        elif interacao.falando:
            gesto = "fala"
        elif interacao.pensando:
            gesto = "pensamento"
        elif interacao.ouvindo:
            gesto = "escuta"
        elif expressao is ExpressaoVisual.RECUPERANDO:
            gesto = "alivio"
        elif reacao_critica:
            gesto = "surpresa"

        estado = resultado.estado_afetivo
        intensidade = max(
            0.0,
            min(
                1.0,
                (
                    estado.ativacao
                    + estado.estresse
                    + estado.engajamento
                    + estado.curiosidade
                ) / 4.0,
            ),
        )
        velocidade = max(0.1, min(1.0, 0.25 + 0.55 * estado.ativacao))
        movimento = max(0.1, min(1.0, 0.2 + 0.5 * intensidade))

        return EstadoVisualAtlas(
            modo=modo,
            expressao=expressao,
            intensidade_expressao=intensidade,
            foco_visual=foco,
            direcao_olhar=foco if foco != "neutro" else "frente",
            gesto_atual=gesto,
            velocidade_movimento=velocidade,
            intensidade_movimento=movimento,
            falando=interacao.falando,
            ouvindo=interacao.ouvindo,
            pensando=interacao.pensando,
            duvida_identidade=interacao.duvida_identidade,
            transicao_ms=160 if reacao_critica else 400,
        )
