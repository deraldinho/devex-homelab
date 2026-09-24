import json
from pathlib import Path

from atlas.config_hermes import load_hermes_config
from atlas.hermes_adapter import HermesAdapter
from atlas.modelo_llm_gateway import SolicitacaoInferencia

def main():
    config_path = Path.home() / "pentium-agent" / "atlas" / "config_hermes.json"
    cfg = load_hermes_config(config_path)
    adapter = HermesAdapter(cfg)

    # Simula exatamente o contexto completo que o cognitive daemon constroi
    contexto_real = {
        "estado_tecnico": "healthy",
        "entidade_principal": "core",
        "mudancas_recentes": [
            {"source": "managed.core", "kind": "status_changed", "severity": "info", "payload": {"status": "ok"}},
            {"source": "managed.x99", "kind": "source_error", "severity": "warning", "payload": {"error": "fan_rpm"}},
            {"source": "human.discord", "kind": "chat", "severity": "info", "payload": {"text": "Olá Atlas"}}
        ],
        "memorias_relevantes": [
            {"content": "O backup do restic e disaster recovery foram homologados com sucesso."}
        ]
    }

    req = SolicitacaoInferencia(
        versao_schema=1,
        tarefa="formular_resposta_cognitiva",
        contexto_json=json.dumps(contexto_real),
        max_tokens_contexto=4096
    )

    print("Testando inferência com contexto real do Discord + Background Telemetria...")
    res = adapter.inferir(req)
    print(f"Sucesso: {res.sucesso}")
    if res.sucesso and res.texto:
        payload = json.loads(res.texto)
        print(f"Texto gerado pelo Hermes: \"{payload.get('texto')}\"")
        print(f"Intencao: {payload.get('intencao')}")
    else:
        print(f"Erro: {res.erro}")

if __name__ == "__main__":
    main()
