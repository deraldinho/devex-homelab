from pathlib import Path
wt=Path(r'C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-v1-always-on-voice\infrastructure\pentium\atlas')
p=wt/'modelo_llm_gateway.py'
s=p.read_text(encoding='utf-8')
s=s.replace('    max_tokens_contexto: int\n','    max_tokens_contexto: int\n    reasoning_mode: str = "off"\n',1)
s=s.replace('        if not isinstance(self.max_tokens_contexto, int) or self.max_tokens_contexto <= 0:\n            raise ValueError("max_tokens_contexto deve ser inteiro > 0")\n','        if not isinstance(self.max_tokens_contexto, int) or self.max_tokens_contexto <= 0:\n            raise ValueError("max_tokens_contexto deve ser inteiro > 0")\n        if self.reasoning_mode not in {"off", "auto", "on"}:\n            raise ValueError("reasoning_mode invalido")\n',1)
p.write_text(s,encoding='utf-8')

p=wt/'llm_gateway.py'; s=p.read_text(encoding='utf-8')
s=s.replace('class LLMGateway:\n    def __init__(self, backend: LLMBackend, *, max_payload_bytes: int, max_tokens_contexto: int):','class LLMGateway:\n    def __init__(self, backend: LLMBackend, *, max_payload_bytes: int, max_tokens_contexto: int, reasoning_policy=None):')
s=s.replace('        self._max_tokens_contexto = int(max_tokens_contexto)\n','        self._max_tokens_contexto = int(max_tokens_contexto)\n        self._reasoning_policy = reasoning_policy\n')
s=s.replace('        solicitacao = SolicitacaoInferencia(1, tarefa.strip(), payload, self._max_tokens_contexto)\n','        mode = self._reasoning_policy.select(contexto, tarefa) if self._reasoning_policy is not None else "off"\n        solicitacao = SolicitacaoInferencia(1, tarefa.strip(), payload, self._max_tokens_contexto, mode)\n')
p.write_text(s,encoding='utf-8')

p=wt/'llama_cpp_backend.py'; s=p.read_text(encoding='utf-8')
s=s.replace('            "-n", "256",\n            "-p", prompt,\n','            "-n", "256",\n            "--single-turn",\n            "--simple-io",\n            "--reasoning", solicitacao.reasoning_mode,\n            "--no-display-prompt",\n            "-p", prompt,\n')
p.write_text(s,encoding='utf-8')

p=wt/'voice_daemon.py'; s=p.read_text(encoding='utf-8')
s=s.replace('from .reaction_loop_cognitivo import ReactionLoopCognitivo\n','from .reaction_loop_cognitivo import ReactionLoopCognitivo\nfrom .reasoning_policy import ReasoningPolicy\n')
s=s.replace('    gateway = LLMGateway(llm_backend, max_payload_bytes=cognitive.contexto.max_payload_bytes,\n                         max_tokens_contexto=int(cfg["llm_context_tokens"]))\n','    gateway = LLMGateway(llm_backend, max_payload_bytes=cognitive.contexto.max_payload_bytes,\n                         max_tokens_contexto=int(cfg["llm_context_tokens"]), reasoning_policy=ReasoningPolicy())\n')
p.write_text(s,encoding='utf-8')
