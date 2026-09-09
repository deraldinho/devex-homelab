from pathlib import Path
import subprocess
from atlas.modelo_llm_gateway import SolicitacaoInferencia
from atlas.prompt_cognitivo import construir_prompt_cognitivo

home = Path.home() / 'pentium-agent'
root = home / 'runtime' / 'llama'
req = SolicitacaoInferencia(1,'teste_fisico','{"mensagem":"responda somente com JSON valido e texto curto"}',512,'off')
prompt = construir_prompt_cognitivo(req)
argv = [str(root/'build/bin/llama-cli'),'-m',str(root/'models/Qwen3-0.6B-Q4_0.gguf'),'-c','512','-n','256','--single-turn','--simple-io','--log-disable','--reasoning','off','--no-display-prompt','-p',prompt]
r = subprocess.run(argv, text=True, capture_output=True, timeout=60, check=False)
probes = home / 'runtime' / 'probes'
(probes/'raw-off.out').write_text(r.stdout, encoding='utf-8')
(probes/'raw-off.err').write_text(r.stderr, encoding='utf-8')
print('RC=', r.returncode, 'STDOUT=', len(r.stdout), 'STDERR=', len(r.stderr))
