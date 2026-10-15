# Atlas / Hermes — NVIDIA NIM fallback (2026-10-14)

## Evidências de homologação

- Host: `pentium`. Provedor principal inalterado: `nous`, modelo `inclusionai/ling-3.0-flash-fin:free`.
- Fallback Hermes: 1. `stepfun/step-5-preview:free` (Nous); 2. `poolside/laguna-s-2.1:free` (Nous); 3. `meituan/longcat-2.5-preview:free` (Nous); 4. `nvidia/nemotron-3.5-lightning-30b-a3b` (NVIDIA).
- URL API: `https://integrate.api.nvidia.com/v1`, endpoint gratuito de prototipagem segundo catálogo NVIDIA, sujeito a termos, quotas e condições da conta.
- Catálogo autenticado NVIDIA: HTTP 200, 80 modelos. `mistralai/mistral-nemotron` não presente; API de inferência retornou HTTP 410. Por isso a tentativa anterior tinha sido atendida pelo fallback Nous.
- Inferência direta com `nvidia/nemotron-3.5-lightning-30b-a3b`: HTTP 200, 23 tokens de entrada, 16 de saída.
- Inferência pelo Hermes: execução de `hermes --provider nvidia --model nvidia/nemotron-3.5-lightning-30b-a3b --ignore-rules --usage-file ... -z 2+2=?`; resposta `4`. Registro: `provider=nvidia`, `model=nvidia/nemotron-3.5-lightning-30b-a3b`, `api_calls=1`, `completed=true`, `failed=false`.
- Telemetria Hermes: `estimated_cost_usd=0.0`, **`cost_status=unknown`**, `cost_source=none`. Isso **não comprova custo real de zero**.
- O cadastro antigo exposto deixou de constar no pool local; revogação remota da chave no painel NVIDIA não pôde ser comprovada.
- Não foram alterados o backend padrão do Atlas, seus serviços em execução ou o túnel OpenCode x99. NVIDIA e OpenCode são rotas independentes.

## Operação e limites

NVIDIA fica na **última posição**, depois dos três modelos Nous. O uso gratuito do NVIDIA Developer Program é destinado a prototipagem, sujeito a limites e termos: confirmar quotas e eventuais cobranças no portal antes de uso continuado/produção. Nenhuma chave, token ou segredo deve ser copiado para este repositório.
