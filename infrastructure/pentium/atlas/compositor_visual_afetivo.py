from __future__ import annotations

from .contexto_foco_emocao import ResultadoFocoEmocao
from .modelo_visual_atlas import EstadoInteracaoVisual, EstadoVisualAtlas, ExpressaoVisual, ModoVisual

_MAPA = {
    # Arquetipo SERENO
    "calmo": ExpressaoVisual.SERENO,
    "sereno": ExpressaoVisual.SERENO,
    "harmonico": ExpressaoVisual.SERENO,
    "satisfeito": ExpressaoVisual.SERENO,
    "confiante": ExpressaoVisual.SERENO,
    "acolhedor": ExpressaoVisual.SERENO,
    "orgulhoso": ExpressaoVisual.SERENO,
    # Arquetipo ENGAJADO
    "interessado": ExpressaoVisual.ENGAJADO,
    "determinado": ExpressaoVisual.ENGAJADO,
    "empolgado": ExpressaoVisual.ENGAJADO,
    # Arquetipo CURIOSO
    "curioso": ExpressaoVisual.CURIOSO,
    "fascinado": ExpressaoVisual.CURIOSO,
    "pensativo": ExpressaoVisual.CURIOSO,
    # Arquetipo ATENTO
    "atento": ExpressaoVisual.ATENTO,
    "vigilante": ExpressaoVisual.ATENTO,
    # Arquetipo PREOCUPADO
    "preocupado": ExpressaoVisual.PREOCUPADO,
    # Arquetipo SOB_PRESSAO
    "estressado": ExpressaoVisual.SOB_PRESSAO,
    "alarmado": ExpressaoVisual.SOB_PRESSAO,
    "frustrado": ExpressaoVisual.SOB_PRESSAO,
    "sobrecarregado": ExpressaoVisual.SOB_PRESSAO,
    "exaurido": ExpressaoVisual.SOB_PRESSAO,
    # Arquetipo RECUPERANDO
    "aliviado": ExpressaoVisual.RECUPERANDO,
}

_POSTURAS_ABERTAS = frozenset({"acolhedor", "harmonico", "satisfeito", "orgulhoso", "aliviado", "calmo", "sereno"})
_POSTURAS_ATENTAS = frozenset({"determinado", "vigilante", "atento", "interessado"})
_POSTURAS_FECHADAS = frozenset({"sobrecarregado", "exaurido", "frustrado", "estressado", "alarmado", "preocupado"})

class CompositorVisualAfetivo:
    def compor(
        self,
        resultado: ResultadoFocoEmocao,
        interacao: EstadoInteracaoVisual,
        *,
        reacao_critica: bool = False,
    ) -> EstadoVisualAtlas:
        emocao_rotulo = resultado.emocao.principal
        expressao = _MAPA.get(emocao_rotulo, ExpressaoVisual.SERENO)
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
        elif expressao is ExpressaoVisual.RECUPERANDO or emocao_rotulo == "aliviado":
            gesto = "alivio"
        elif reacao_critica or emocao_rotulo == "alarmado":
            gesto = "surpresa"
        elif emocao_rotulo in ("acolhedor", "orgulhoso"):
            gesto = "aceno"
        elif emocao_rotulo in ("determinado", "empolgado"):
            gesto = "aberto"
        elif emocao_rotulo in ("vigilante", "atento"):
            gesto = "escuta"

        # Postura Semântica
        if emocao_rotulo in _POSTURAS_ABERTAS:
            postura = "ABERTO"
        elif emocao_rotulo in _POSTURAS_ATENTAS:
            postura = "ATENTO"
        elif emocao_rotulo in _POSTURAS_FECHADAS:
            postura = "FECHADO"
        else:
            postura = "NEUTRO"

        # Atenção aos Nós e Locomoção
        alvo_locomocao = "auto"
        lado_gesto = "none"
        if foco != "neutro":
            alvo_locomocao = foco
            if foco in ("core", "mikrotik"):
                lado_gesto = "left"
            elif foco in ("x99",):
                lado_gesto = "right"
            elif foco in ("pentium", "deraldinho"):
                lado_gesto = "both"

        # Comportamento Pet Shimeji
        if reacao_critica:
            acao_pet = "POKE"
        elif interacao.falando or interacao.ouvindo:
            acao_pet = "SIT"
        elif modo is ModoVisual.OBSERVANDO and foco in ("core", "x99", "mikrotik"):
            acao_pet = "HOP"
        else:
            acao_pet = "PATROL"

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
            postura_atual=postura,
            lado_gesto=lado_gesto,
            alvo_locomocao=alvo_locomocao,
            acao_pet=acao_pet,
            emocao_principal=emocao_rotulo,
            nuances_emocionais=resultado.emocao.nuances,
        )

