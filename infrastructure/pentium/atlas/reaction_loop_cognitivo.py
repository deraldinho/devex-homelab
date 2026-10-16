from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .modelo_contexto_cognitivo import MotivoAtivacaoCognitiva
from .saida_cognitiva import parse_resposta_llm
from .conversational_fallback import safe_natural_reply


@dataclass(frozen=True)
class RespostaCognitiva:
    ativado: bool
    motivo: str | None
    texto: str | None
    razao: str | None
    backend: str | None
    duracao_ms: int | None
    resumo: str | None = None
    intencao: str | None = None
    parametros_intencao: dict[str, object] | None = None
    confianca: float | None = None
    requer_confirmacao: bool = False
    intencao_autorizada: bool = False
    solicitar_fala: bool = False


class ReactionLoopCognitivo:
    def __init__(self, policy, builder, gateway, *, capability_policy=None, memory_retriever=None, workspace_retriever=None, cognitive_cache=None):
        self._policy = policy
        self._builder = builder
        self._gateway = gateway
        self._capability_policy = capability_policy
        self._memory_retriever = memory_retriever
        self._workspace_retriever = workspace_retriever
        self._cognitive_cache = cognitive_cache
    def processar(self, *, fingerprint: str, agora: str,
                 sinais_ativacao: Mapping[str, Any], dados_contexto: Mapping[str, Any],
                 on_inference: Callable[[bool], None] | None = None) -> RespostaCognitiva:
        decisao = self._policy.avaliar(
            fingerprint=fingerprint,
            agora=agora,
            **dict(sinais_ativacao),
        )
        if not decisao.ativar:
            return RespostaCognitiva(
                False, None, None, decisao.razao_bloqueio, None, None
            )

        motivo = decisao.motivo
        dados_builder = dict(dados_contexto)
        # O fingerprint pode ser somente um UUID de estimulo. Para interacoes
        # humanas, pesquisar memoria pelo texto efetivo melhora o recall.
        # Aceitar apenas mensagens de fontes human.* (nao logs/telemetria).
        consulta = fingerprint
        if motivo is MotivoAtivacaoCognitiva.INTERACAO_HUMANA:
            mensagem = dados_builder.get("mensagem_usuario")
            if not isinstance(mensagem, str):
                mensagem = ""
            if not mensagem.strip():
                recentes = dados_builder.get("mudancas_recentes")
                if isinstance(recentes, (list, tuple)):
                    for evento in reversed(recentes[-16:]):
                        # Estimulos reais chegam como objeto de dados (Stimulus),
                        # nao como Mapping; aceitar os dois formatos preserva a
                        # busca de memoria pelo texto efetivo do operador.
                        if isinstance(evento, Mapping):
                            source = evento.get("source", "")
                            payload = evento.get("payload")
                        else:
                            source = getattr(evento, "source", "")
                            payload = getattr(evento, "payload", None)
                        if not str(source).startswith("human."):
                            continue
                        if not isinstance(payload, Mapping):
                            continue
                        candidate = payload.get("text") or payload.get("message")
                        if isinstance(candidate, str) and candidate.strip():
                            mensagem = candidate
                            break
            if mensagem.strip():
                consulta = mensagem.strip()[:512]
        termos_busca = (consulta, motivo.value if motivo is not None else "")
        memorias_relevantes = ()
        if self._memory_retriever is not None:
            incidente = dados_builder.get("incidente")
            percepcao = dados_builder.get("percepcao")
            entidade_id = getattr(incidente, "entidade_principal", None) or getattr(percepcao, "entidade_id", None)
            try:
                memorias_relevantes = self._memory_retriever.retrieve(
                    entity_id=entidade_id,
                    query_terms=termos_busca,
                )
            except Exception:
                memorias_relevantes = ()
        dados_builder["memorias_relevantes"] = memorias_relevantes
        workspace_relevante = ()
        if self._workspace_retriever is not None:
            try:
                query = " ".join(part for part in termos_busca if part)
                workspace_relevante = self._workspace_retriever.retrieve(query, max_items=4, max_bytes=2048)
            except Exception:
                workspace_relevante = ()
        dados_builder["workspace_relevante"] = workspace_relevante
        contexto = self._builder.construir(
            motivo=motivo,
            agora=agora,
            **dados_builder,
        )
        autonomo = motivo is not MotivoAtivacaoCognitiva.INTERACAO_HUMANA
        self._policy.registrar_ativacao(fingerprint, agora, autonomo)
        tarefa = "formular_resposta_cognitiva"
        cache_permitido = False
        resultado = None
        if self._cognitive_cache is not None:
            try:
                cache_permitido = self._cognitive_cache.allowed(motivo)
                if cache_permitido:
                    resultado = self._cognitive_cache.get(contexto, tarefa)
            except Exception:
                cache_permitido = False
                resultado = None
        cache_hit = resultado is not None
        if resultado is None:
            try:
                if on_inference is not None:
                    on_inference(True)
                resultado = self._gateway.inferir(contexto, tarefa)
            finally:
                if on_inference is not None:
                    on_inference(False)

        if not resultado.sucesso:
            return RespostaCognitiva(
                True,
                motivo.value if motivo is not None else None,
                None,
                "cognitive_backend_unavailable",
                resultado.backend,
                resultado.duracao_ms,
            )

        try:
            estruturada = parse_resposta_llm(resultado.texto or "")
        except ValueError:
            estruturada = None

        if cache_permitido and not cache_hit and estruturada is not None and estruturada.intencao is None:
            try:
                self._cognitive_cache.put(contexto, tarefa, resultado)
            except Exception:
                pass

        if self._capability_policy is None:
            # Missing capability policy means there is NO action authority.
            # Never echo structured action directives into presentation.
            if estruturada is not None and estruturada.intencao is not None:
                return RespostaCognitiva(
                    True, motivo.value if motivo is not None else None,
                    None, "capability_policy_unavailable",
                    resultado.backend, resultado.duracao_ms,
                )
            if estruturada is None:
                # Compatibility: older read-only narrator sessions have no
                # capability policy and may produce prose. Validate it with
                # the same bounded conversational filter instead of echoing
                # arbitrary instructions, credentials or markup.
                natural = safe_natural_reply(resultado.texto)
                if natural is None:
                    return RespostaCognitiva(
                        True, motivo.value if motivo is not None else None,
                        None, "saida_llm_invalida",
                        resultado.backend, resultado.duracao_ms,
                    )
                return RespostaCognitiva(
                    True, motivo.value if motivo is not None else None,
                    natural, None, resultado.backend, resultado.duracao_ms,
                    resumo="resposta_natural_sem_intencao",
                    intencao=None, parametros_intencao={},
                    requer_confirmacao=False, intencao_autorizada=False,
                )

        if estruturada is None:
            # Plain LLM prose may answer a HUMAN; it may NEVER authorize an action.
            # System incidents and self-work remain strict structured JSON only.
            natural = (safe_natural_reply(resultado.texto)
                       if motivo is MotivoAtivacaoCognitiva.INTERACAO_HUMANA else None)
            if natural is not None:
                return RespostaCognitiva(
                    True, motivo.value, natural, None, resultado.backend,
                    resultado.duracao_ms, resumo="resposta_natural_sem_intencao",
                    intencao=None, parametros_intencao={}, requer_confirmacao=False,
                    intencao_autorizada=False,
                )
            return RespostaCognitiva(
                True,
                motivo.value if motivo is not None else None,
                None,
                "saida_llm_invalida",
                resultado.backend,
                resultado.duracao_ms,
            )

        autorizada = False
        requer_confirmacao = estruturada.requer_confirmacao
        if estruturada.intencao is not None:
            decisao_cap = self._capability_policy.avaliar(
                estruturada.intencao,
                estruturada.parametros_intencao,
            )
            autorizada = decisao_cap.autorizada
            requer_confirmacao = requer_confirmacao or decisao_cap.requer_confirmacao

        return RespostaCognitiva(
            True,
            motivo.value if motivo is not None else None,
            estruturada.texto,
            None,
            resultado.backend,
            resultado.duracao_ms,
            estruturada.resumo,
            estruturada.intencao,
            estruturada.parametros_intencao,
            estruturada.confianca,
            requer_confirmacao,
            autorizada,
        )
