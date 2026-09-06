from __future__ import annotations

from .modelo_llm_gateway import SolicitacaoInferencia


def construir_prompt_cognitivo(solicitacao: SolicitacaoInferencia) -> str:
    if not isinstance(solicitacao, SolicitacaoInferencia):
        raise TypeError("solicitacao deve ser SolicitacaoInferencia")
    return (
        "Tarefa versionada: " + solicitacao.tarefa + "\n"
        "Use apenas o contexto JSON fornecido. Nao invente estado tecnico. "
        "Nao decida saude tecnica, autorizacao ou execucao de capability.\n"
        "Responda SOMENTE um objeto JSON, sem markdown e sem texto externo, com exatamente estes campos:\n"
        '{"versao_schema":1,"texto":null,"resumo":null,"intencao":null,'
        '"parametros_intencao":{},"confianca":0.0,"motivo":"motivo_ativacao",'
        '"requer_confirmacao":false}\n'
        "Quando nao houver intencao operacional, use intencao=null e parametros_intencao={}. "
        "O campo motivo deve refletir o motivo_ativacao recebido no contexto.\n"
        "Contexto JSON:\n" + solicitacao.contexto_json
    )
