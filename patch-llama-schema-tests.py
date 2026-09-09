from pathlib import Path
p=Path(r'C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-v1-always-on-voice\infrastructure\pentium\atlas\tests\test_v1_llama_schema.py')
t=p.read_text(encoding='utf-8')
t=t.replace('self.assertIn("root ::= object", grammar)','self.assertIn("versao_schema", grammar)')
t=t.replace("self.assertIn('\"motivo\"', _JSON_GBNF)","self.assertIn('motivo', _JSON_GBNF)")
t=t.replace("self.assertIn('\"parametros_intencao\"', _JSON_GBNF)","self.assertIn('parametros_intencao', _JSON_GBNF)")
p.write_text(t,encoding='utf-8')
