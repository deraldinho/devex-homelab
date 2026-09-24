import sys
import json
from pathlib import Path

from atlas.config_hermes import load_hermes_config
from atlas.hermes_adapter import HermesAdapter
from atlas.modelo_llm_gateway import SolicitacaoInferencia

def main():
    config_path = Path.home() / "pentium-agent" / "atlas" / "config_hermes.json"
    cfg = load_hermes_config(config_path)
    adapter = HermesAdapter(cfg)
    req = SolicitacaoInferencia(
        versao_schema=1,
        tarefa="formular_resposta_cognitiva",
        contexto_json=json.dumps({
            "canal": "discord",
            "mensagem_usuario": "Olá Atlas"
        }),
        max_tokens_contexto=4096
    )
    print("Testando saudacao 'Olá Atlas' no Hermes...")
    res = adapter.inferir(req)
    print(f"Sucesso: {res.sucesso}")
    if res.sucesso and res.texto:
        payload = json.loads(res.texto)
        print(f"Texto: {payload.get('texto')}")
        print(f"Intencao: {payload.get('intencao')}")
    else:
        print(f"Erro: {res.erro}")

if __name__ == "__main__":
    main()
