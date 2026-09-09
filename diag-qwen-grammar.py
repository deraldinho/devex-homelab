from pathlib import Path
import subprocess
from atlas.llama_cpp_backend import _JSON_GBNF
from atlas.prompt_cognitivo import construir_prompt_cognitivo
from atlas.modelo_llm_gateway import SolicitacaoInferencia
root=Path.home()/'pentium-agent'/'runtime'/'llama'
req=SolicitacaoInferencia(1,'teste_fisico','{"mensagem":"responda curto confirmando que esta ouvindo"}',512,'off')
prompt=construir_prompt_cognitivo(req)
argv=[str(root/'build/bin/llama-cli'),'-m',str(root/'models/Qwen3-0.6B-Q4_0.gguf'),'-c','512','-n','256','--single-turn','--simple-io','--log-disable','--temp','0','--grammar',_JSON_GBNF,'--reasoning','off','--no-display-prompt','-p',prompt]
proc=subprocess.run(argv,text=True,capture_output=True,timeout=90,check=False)
print('RC',proc.returncode,'OUT',len(proc.stdout),'ERR',len(proc.stderr))
print(proc.stdout)
print('---ERR---')
print(proc.stderr)
