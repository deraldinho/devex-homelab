from pathlib import Path
from atlas.llama_cpp_backend import _extract_cognitive_json
p = Path.home() / 'pentium-agent/runtime/probes/raw-off.out'
s = p.read_text(encoding='utf-8')
print(_extract_cognitive_json(s))
