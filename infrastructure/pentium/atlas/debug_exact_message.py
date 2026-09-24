import json
from pathlib import Path

from atlas.config_hermes import load_hermes_config
from atlas.hermes_adapter import HermesAdapter
from atlas.modelo_llm_gateway import SolicitacaoInferencia

def main():
    cfg = load_hermes_config(Path.home() / "pentium-agent" / "atlas" / "config_hermes.json")
    adapter = HermesAdapter(cfg)

    msg = "[SUPERADMIN] - xBurg: <@&1489449917394194505> como está a saúde dos nossos servidores e o status dos backups hoje?"
    
    # Vamos inspecionar exatamente o prompt gerado
    req = SolicitacaoInferencia(
        versao_schema=1,
        tarefa="formular_resposta_cognitiva",
        contexto_json=json.dumps({
            "estado_tecnico": "healthy",
            "entidade_principal": "core",
            "mudancas_recentes": [
                {"source": "human.discord", "kind": "chat", "severity": "info", "payload": {"text": msg}}
            ],
            "memorias_relevantes": [
                {"content": "O backup do restic e disaster recovery foram homologados com sucesso."}
            ]
        }),
        max_tokens_contexto=4096
    )

    prompt = adapter._prompt(req)
    print("=== PROMPT ENVIADO AO HERMES ===")
    print(prompt[:600])
    print("...\n=== FIM DO PROMPT ===")

    print("\nInvocando inferencia no Pentium...")
    res = adapter.inferir(req)
    print(f"Sucesso: {res.sucesso}")
    print(f"Texto gerado: {res.texto}")

if __name__ == "__main__":
    main()
