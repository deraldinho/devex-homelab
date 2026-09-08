from __future__ import annotations

import os
import sys


class AtlasChatCli:
    def __init__(self, gateway, *, status_provider):
        self._gateway = gateway
        self._status_provider = status_provider
        self.should_exit = False

    def process_line(self, line: str) -> str | None:
        text = str(line).strip()
        if not text:
            return ""
        if text == "/exit":
            self.should_exit = True
            return None
        if text == "/help":
            return "Comandos: /status, /help, /exit"
        if text == "/status":
            return f"Atlas: {self._status_provider()}"
        if text.startswith("/"):
            return "Comando desconhecido. Use /help."
        return self._gateway.handle(text, source="human.cli")

def _build_gateway():
    from pathlib import Path
    from .capability_registry import atlas_capability_registry
    from .configuracao_cognitiva import carregar_configuracao_cognitiva
    from .contexto_cognitivo import ContextoCognitivoBuilder
    from .human_context import HumanContextProvider
    from .human_interaction import HumanInteractionGateway
    from .llama_cpp_backend import LlamaCppBackend
    from .llm_gateway import LLMGateway
    from .policy_capabilities import PolicyCapabilities
    from .politica_ativacao_cognitiva import ActivationPolicy
    from .reaction_loop_cognitivo import ReactionLoopCognitivo
    from .reasoning_policy import ReasoningPolicy
    from .voice_daemon import ROOT, load_voice_config, _path

    cfg = load_voice_config()
    cognitive = carregar_configuracao_cognitiva(ROOT / 'config_cognitiva.json')
    runtime_root = Path.home() / 'pentium-agent' / 'runtime'
    backend = LlamaCppBackend(runtime_root / 'llama/build/bin/llama-cli', _path(cfg['llm_model']),
                              timeout_s=float(cfg['llm_timeout_s']), max_saida_bytes=8192)
    gateway = LLMGateway(backend, max_payload_bytes=cognitive.contexto.max_payload_bytes,
                         max_tokens_contexto=int(cfg['llm_context_tokens']), reasoning_policy=ReasoningPolicy())
    loop = ReactionLoopCognitivo(ActivationPolicy(cognitive.ativacao), ContextoCognitivoBuilder(cognitive.contexto),
                                 gateway, capability_policy=PolicyCapabilities(atlas_capability_registry(),
                                 read_auto_allow=('get_host_status',), control_allow=()))
    expected_sha = (
        os.environ.get('ATLAS_EXPECTED_SHA') or None
        if cognitive.observation_bridge.require_expected_sha else None
    )
    context_provider = HumanContextProvider(
        _path(cfg['health_path']),
        _path(cognitive.observation_bridge.snapshot_path),
        max_snapshot_age_s=cognitive.observation_bridge.max_snapshot_age_s,
        expected_sha=expected_sha,
    )
    return HumanInteractionGateway(loop, context_provider=context_provider,
                                   max_text_chars=cognitive.contexto.max_string_chars)

def main() -> int:
    gateway = _build_gateway()
    cli = AtlasChatCli(gateway, status_provider=lambda: 'READY')
    print('Atlas CLI. Use /help para comandos.', flush=True)
    for line in sys.stdin:
        output = cli.process_line(line)
        if output:
            print(output, flush=True)
        if cli.should_exit:
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
