from pathlib import Path
p = Path(r'C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-v1-always-on-voice\infrastructure\pentium\atlas\llama_cpp_backend.py')
t = p.read_text(encoding='utf-8')
t = t.replace('import subprocess\nimport time\n', 'import json\nimport subprocess\nimport time\n', 1)
insert = '''\n_COGNITIVE_KEYS = {"versao_schema","texto","resumo","intencao","parametros_intencao","confianca","motivo","requer_confirmacao"}\n\ndef _extract_cognitive_json(stdout: str) -> str | None:\n    decoder = json.JSONDecoder()\n    matches = []\n    for idx, ch in enumerate(stdout):\n        if ch != "{":\n            continue\n        try:\n            value, end = decoder.raw_decode(stdout[idx:])\n        except json.JSONDecodeError:\n            continue\n        if isinstance(value, dict) and _COGNITIVE_KEYS.issubset(value.keys()):\n            matches.append(json.dumps(value, ensure_ascii=False, separators=(",", ":")))\n    return matches[-1] if matches else None\n'''
needle = 'from .prompt_cognitivo import construir_prompt_cognitivo\n\n\nclass LlamaCppBackend:'
if needle not in t:
    raise SystemExit('needle not found')
t = t.replace(needle, 'from .prompt_cognitivo import construir_prompt_cognitivo\n' + insert + '\nclass LlamaCppBackend:', 1)
old = '        texto = stdout.strip()\n        if not texto:\n            return self._falha(ErroInferencia.SAIDA_INVALIDA, inicio)\n        return ResultadoInferencia(True, texto, None, max(0, int((time.monotonic() - inicio) * 1000)), "llama_cpp")'
new = '        texto = _extract_cognitive_json(stdout)\n        if not texto:\n            return self._falha(ErroInferencia.SAIDA_INVALIDA, inicio)\n        return ResultadoInferencia(True, texto, None, max(0, int((time.monotonic() - inicio) * 1000)), "llama_cpp")'
if old not in t:
    raise SystemExit('return needle not found')
p.write_text(t.replace(old, new, 1), encoding='utf-8')
