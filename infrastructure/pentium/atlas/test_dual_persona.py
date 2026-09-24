import json
from pathlib import Path

from atlas.config_hermes import load_hermes_config
from atlas.hermes_adapter import HermesAdapter
from atlas.modelo_llm_gateway import SolicitacaoInferencia

def test_greeting(adapter):
    print("\n--- CASO 1: Saudacao Casual ('Olá Atlas') ---")
    req = SolicitacaoInferencia(
        versao_schema=1,
        tarefa="formular_resposta_cognitiva",
        contexto_json=json.dumps({
            "estado_tecnico": "healthy",
            "mudancas_recentes": [
                {"source": "human.discord", "kind": "chat", "severity": "info", "payload": {"text": "Olá Atlas"}}
            ],
            "memorias_relevantes": []
        }),
        max_tokens_contexto=4096
    )
    res = adapter.inferir(req)
    if res.sucesso and res.texto:
        payload = json.loads(res.texto)
        print(f"Resposta Casual: \"{payload.get('texto')}\"")
        print(f"Intencao: {payload.get('intencao')}")

def test_infra_question(adapter):
    print("\n--- CASO 2: Pergunta Tecnica ('Atlas, qual o status dos nossos servidores?') ---")
    req = SolicitacaoInferencia(
        versao_schema=1,
        tarefa="formular_resposta_cognitiva",
        contexto_json=json.dumps({
            "estado_tecnico": "healthy",
            "entidade_principal": "pentium",
            "mudancas_recentes": [
                {"source": "managed.core", "kind": "status_changed", "severity": "info", "payload": {"status": "online"}},
                {"source": "managed.x99", "kind": "source_error", "severity": "warning", "payload": {"error": "fan_rpm"}},
                {"source": "human.discord", "kind": "chat", "severity": "info", "payload": {"text": "Atlas, qual o status dos nossos servidores?"}}
            ],
            "memorias_relevantes": [
                {"content": "O cluster opera com Pentium como host de controle e Core/x99 como compute."}
            ]
        }),
        max_tokens_contexto=4096
    )
    res = adapter.inferir(req)
    if res.sucesso and res.texto:
        payload = json.loads(res.texto)
        print(f"Resposta Tecnica: \"{payload.get('texto')}\"")
        print(f"Intencao: {payload.get('intencao')}")

def main():
    cfg = load_hermes_config(Path.home() / "pentium-agent" / "atlas" / "config_hermes.json")
    adapter = HermesAdapter(cfg)
    test_greeting(adapter)
    test_infra_question(adapter)

if __name__ == "__main__":
    main()
