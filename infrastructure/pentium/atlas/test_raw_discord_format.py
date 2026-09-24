import json
from pathlib import Path

from atlas.config_hermes import load_hermes_config
from atlas.hermes_adapter import HermesAdapter
from atlas.modelo_llm_gateway import SolicitacaoInferencia

def main():
    cfg = load_hermes_config(Path.home() / "pentium-agent" / "atlas" / "config_hermes.json")
    adapter = HermesAdapter(cfg)

    # Mensagem exatamente no formato em que o Discord Gateway entrega
    msg_raw = "[SUPERADMIN] - xBurg: <@1489448566081458298> Atlas, o que você acha da ideia de usarmos gRPC em vez de REST para a comunicação interna entre nossos servidores?"
    print(f"Testando mensagem bruta vinda do Discord:\n  '{msg_raw}'\n")

    req = SolicitacaoInferencia(
        versao_schema=1,
        tarefa="formular_resposta_cognitiva",
        contexto_json=json.dumps({
            "estado_tecnico": "healthy",
            "mudancas_recentes": [
                {"source": "human.discord", "kind": "chat", "severity": "info", "payload": {"text": msg_raw}}
            ],
            "memorias_relevantes": []
        }),
        max_tokens_contexto=4096
    )

    res = adapter.inferir(req)
    print(f"Sucesso: {res.sucesso}")
    if res.sucesso and res.texto:
        payload = json.loads(res.texto)
        print(f"\nResposta gerada pelo Atlas / JARVIS:\n\"{payload.get('texto')}\"")
        print(f"\nIntencao: {payload.get('intencao')}")
    else:
        print(f"Erro: {res.erro}")

if __name__ == "__main__":
    main()
