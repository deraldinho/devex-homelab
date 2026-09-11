from __future__ import annotations

from .modelo_visual_atlas import EstadoInteracaoVisual


class AffectiveRuntime:
    def __init__(self, compositor, publisher, *, interacao_inicial: EstadoInteracaoVisual):
        self._compositor = compositor
        self._publisher = publisher
        self._interacao = interacao_inicial
        self._cognicao = EstadoInteracaoVisual(atualizado_em=interacao_inicial.atualizado_em)
        self._ultimo_resultado = None
        self.ultimo_visual = None
        self.ultimo_erro_publicacao = None
        self.ultimo_erro_composicao = None

    def _recompor(self, *, reacao_critica: bool = False):
        if self._ultimo_resultado is None:
            return self.ultimo_visual
        try:
            efetiva = EstadoInteracaoVisual(
                ouvindo=self._interacao.ouvindo,
                pensando=self._interacao.pensando or self._cognicao.pensando,
                falando=self._interacao.falando,
                duvida_identidade=self._interacao.duvida_identidade or self._cognicao.duvida_identidade,
                degradado=self._interacao.degradado or self._cognicao.degradado,
                atualizado_em=max(self._interacao.atualizado_em, self._cognicao.atualizado_em),
            )
            visual = self._compositor.compor(
                self._ultimo_resultado,
                efetiva,
                reacao_critica=reacao_critica,
            )
            self.ultimo_erro_composicao = None
        except Exception as exc:
            self.ultimo_erro_composicao = exc
            return self.ultimo_visual

        if visual == self.ultimo_visual:
            return visual

        self.ultimo_visual = visual
        try:
            self._publisher.publicar(visual)
            self.ultimo_erro_publicacao = None
        except Exception as exc:
            self.ultimo_erro_publicacao = exc
        return visual

    def atualizar_resultado(self, resultado, *, reacao_critica: bool = False):
        self._ultimo_resultado = resultado
        return self._recompor(reacao_critica=reacao_critica)

    def atualizar_interacao(self, interacao: EstadoInteracaoVisual):
        self._interacao = interacao
        if self._ultimo_resultado is None:
            return None
        return self._recompor()

    def atualizar_cognicao(self, interacao: EstadoInteracaoVisual):
        self._cognicao = interacao
        if self._ultimo_resultado is None:
            return None
        return self._recompor()
