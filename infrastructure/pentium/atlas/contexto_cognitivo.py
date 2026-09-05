from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .configuracao_cognitiva import PoliticaContextoCognitivo
from .modelo_contexto_cognitivo import ContextoCognitivo, MotivoAtivacaoCognitiva


class ContextoCognitivoBuilder:
    def __init__(self, politica: PoliticaContextoCognitivo):
        self._politica = politica

    def _string(self, valor: str | None, campo: str, truncamentos: list[str]) -> str | None:
        if valor is None:
            return None
        texto = str(valor)
        if len(texto) > self._politica.max_string_chars:
            truncamentos.append(f"string:{campo}")
            return texto[: self._politica.max_string_chars]
        return texto

    def _reduzir_payload(self, valor: Any, prefixo: str, truncamentos: list[str]) -> Any:
        if isinstance(valor, str):
            return self._string(valor, prefixo, truncamentos)
        if isinstance(valor, dict):
            return {str(k): self._reduzir_payload(v, f"{prefixo}.{k}", truncamentos) for k, v in valor.items()}
        if isinstance(valor, (list, tuple)):
            return [self._reduzir_payload(v, prefixo, truncamentos) for v in valor]
        return valor

    def construir(self, *, motivo, assessment, percepcao, incidente, estado_afetivo, emocao, foco,
                  expectativa, mudancas_recentes, dependencias_afetadas, agora) -> ContextoCognitivo:
        truncamentos: list[str] = []
        entidade = incidente.entidade_principal if incidente is not None else percepcao.entidade_id
        if not entidade and foco.principal is not None:
            entidade = foco.principal.entidade_id

        mudancas = tuple(mudancas_recentes[: self._politica.max_mudancas_recentes])
        if len(mudancas_recentes) > len(mudancas):
            truncamentos.append("mudancas_recentes")

        dependencias = tuple(dependencias_afetadas[: self._politica.max_dependencias_afetadas])
        if len(dependencias_afetadas) > len(dependencias):
            truncamentos.append("dependencias_afetadas")

        nuances = tuple(emocao.nuances[: self._politica.max_nuances])
        if len(emocao.nuances) > len(nuances):
            truncamentos.append("nuances")

        incidente_reduzido = None
        if incidente is not None:
            incidente_reduzido = {
                "incidente_id": incidente.incidente_id,
                "tipo": incidente.tipo,
                "gravidade": incidente.gravidade,
                "causa_provavel": incidente.causa_provavel,
                "confianca_causal": incidente.confianca_causal,
                "estado_recuperacao": incidente.estado_recuperacao.value,
            }

        expectativa_reduzida = None
        if expectativa is not None:
            expectativa_reduzida = {
                "expectativa_id": expectativa.expectativa_id,
                "entidade_id": expectativa.entidade_id,
                "tipo": expectativa.tipo.value,
                "limite_em": expectativa.limite_em,
            }

        mudancas_reduzidas = tuple(
            self._reduzir_payload(
                {
                    "stimulus_id": item.stimulus_id,
                    "source": item.source,
                    "kind": item.kind,
                    "severity": item.severity.value,
                    "novelty": item.novelty,
                    "payload": dict(item.payload),
                },
                f"mudancas_recentes[{indice}]",
                truncamentos,
            )
            for indice, item in enumerate(mudancas)
        )

        estado_afetivo_reduzido = {
            "valencia": estado_afetivo.valencia,
            "ativacao": estado_afetivo.ativacao,
            "estresse": estado_afetivo.estresse,
            "confianca": estado_afetivo.confianca,
            "engajamento": estado_afetivo.engajamento,
            "curiosidade": estado_afetivo.curiosidade,
            "foco_atencao": estado_afetivo.foco_atencao,
        }

        ctx = ContextoCognitivo(
            versao_schema=1,
            timestamp=agora,
            motivo_ativacao=motivo,
            entidade_principal=self._string(entidade, "entidade_principal", truncamentos),
            estado_tecnico=assessment.state.value,
            estado_percepcao=percepcao.estado.value,
            incidente_principal=self._reduzir_payload(incidente_reduzido, "incidente", truncamentos) if incidente_reduzido else None,
            estado_afetivo=self._reduzir_payload(estado_afetivo_reduzido, "estado_afetivo", truncamentos),
            emocao_principal=self._string(emocao.principal, "emocao_principal", truncamentos),
            nuances=tuple(self._string(x, "nuance", truncamentos) for x in nuances),
            foco_atencao=self._string(foco.principal.assunto_id if foco.principal else None, "foco_atencao", truncamentos),
            expectativa=self._reduzir_payload(expectativa_reduzida, "expectativa", truncamentos) if expectativa_reduzida else None,
            mudancas_recentes=mudancas_reduzidas,
            dependencias_afetadas=tuple(self._string(x, "dependencia", truncamentos) for x in dependencias),
            truncamentos=tuple(truncamentos),
        )

        while ctx.payload_bytes() > self._politica.max_payload_bytes and ctx.mudancas_recentes:
            truncamentos.append("payload:mudancas_recentes")
            ctx = ContextoCognitivo(**{
                **ctx.__dict__,
                "mudancas_recentes": ctx.mudancas_recentes[:-1],
                "truncamentos": tuple(truncamentos),
            })
        while ctx.payload_bytes() > self._politica.max_payload_bytes and ctx.dependencias_afetadas:
            truncamentos.append("payload:dependencias_afetadas")
            ctx = ContextoCognitivo(**{
                **ctx.__dict__,
                "dependencias_afetadas": ctx.dependencias_afetadas[:-1],
                "truncamentos": tuple(truncamentos),
            })
        if ctx.payload_bytes() > self._politica.max_payload_bytes:
            raise ValueError("contexto cognitivo excede max_payload_bytes com campos obrigatorios")
        return ctx
