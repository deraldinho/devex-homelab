from pathlib import Path
p = Path(r'C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-v1-always-on-voice\infrastructure\pentium\atlas\tests\test_llama_cpp_backend.py')
t = p.read_text(encoding='utf-8')
valid = '{"versao_schema":1,"texto":"ok","resumo":null,"intencao":null,"parametros_intencao":{},"confianca":0.9,"motivo":"ok","requer_confirmacao":false}'
old = 'stdout="resposta local"'
if old not in t:
    raise SystemExit('fixture not found')
p.write_text(t.replace(old, f'stdout={valid!r}', 1), encoding='utf-8')
