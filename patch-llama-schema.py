from pathlib import Path
p = Path(r'C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-v1-always-on-voice\infrastructure\pentium\atlas\llama_cpp_backend.py')
t = p.read_text(encoding='utf-8')
anchor = '_COGNITIVE_KEYS = {"versao_schema","texto","resumo","intencao","parametros_intencao","confianca","motivo","requer_confirmacao"}\n'
schema = '''_COGNITIVE_JSON_SCHEMA = json.dumps({
    "type":"object","additionalProperties":False,
    "required":["versao_schema","texto","resumo","intencao","parametros_intencao","confianca","motivo","requer_confirmacao"],
    "properties":{
        "versao_schema":{"const":1},
        "texto":{"type":["string","null"]},"resumo":{"type":["string","null"]},
        "intencao":{"type":["string","null"]},"parametros_intencao":{"type":"object"},
        "confianca":{"type":"number","minimum":0,"maximum":1},"motivo":{"type":"string"},
        "requer_confirmacao":{"type":"boolean"}
    }
}, separators=(",", ":"))
'''
if '_COGNITIVE_JSON_SCHEMA' not in t:
    t = t.replace(anchor, anchor + schema, 1)
needle = '            "--log-disable",\n            "--reasoning", solicitacao.reasoning_mode,\n            "--no-display-prompt",\n'
replacement = '            "--log-disable",\n            "--temp", "0",\n            "--json-schema", _COGNITIVE_JSON_SCHEMA,\n            "--reasoning", solicitacao.reasoning_mode,\n            "--no-display-prompt",\n'
if needle not in t:
    raise SystemExit('argv needle not found')
p.write_text(t.replace(needle, replacement, 1), encoding='utf-8')
