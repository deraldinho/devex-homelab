# Atlas / Hermes — fallback gratuito ampliado (2026-10-15)

## Resultado confirmado em pentium

- Principal inalterado: `nous / inclusionai/ling-3.0-flash-fin:free`.
- Cadeia Hermes passou de **4 para 12 fallbacks**:
  1. `nous / stepfun/step-5-preview:free`
  2. `nous / poolside/laguna-s-2.1:free`
  3. `nous / meituan/longcat-2.5-preview:free`
  4. `nous / upstage/solar-mini4:free`
  5. `nous / poolside/laguna-xs-2.1:free`
  6. `nous / stepfun/step-3.7-flash:free`
  7. `nvidia / nvidia/nemotron-3.5-lightning-30b-a3b`
  8. `nvidia / google/gemma-4-31b-it`
  9. `nvidia / openai/gpt-oss-20b`
  10. `nvidia / nvidia/nemotron-3-super-120b-a12b`
  11. `nvidia / meta/muse-glimmer-30b`
  12. `nvidia / nvidia/nemotron-3-ultra-550b-a55b`

## Evidências da seleção

- Nous Portal `/api/nous/recommended-models` retornou HTTP 200 com as novas entradas marcadas `:free`.
- Cada um dos três novos Nous foi testado via `hermes -z`: `completed=true`, `failed=false`, `provider=nous`, `cost_est=0.0`. Preço é estimado, não fatura.
- NVIDIA `/v1/models` retornou 80 modelos para a credencial existente. Os cinco novos selecionados responderam HTTP 200 em `/v1/chat/completions` com teste de poucas dezenas de tokens; o Nemotron Lightning já tinha sido validado anteriormente.
- Candidatos NÃO adicionados porque a tentativa retornou 503/timeout: `poolside/laguna-xs-2.1`, `z-ai/glm-5.3-flash`, `moonshotai/kimi-k3`, `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` **na rota NVIDIA**. (A versão Nous do Laguna XS respondeu.)
- Os NVIDIA escolhidos estavam anunciados com **Free Endpoint** para prototipagem pela NVIDIA; isso não garante acesso ilimitado, quota disponível futura, licença de produção nem ausência de cobrança em outros endpoints.
- Sem credenciais no repositório. `~/.hermes/config.yaml` foi atualizado com gravação atômica e backup local, não com `git add` dos segredos.
- Backup local criado: `~/.hermes/backups/atlas-fallback-before-20261015T032648Z.yaml`.
- Comando `hermes fallback list` no host mostrou as 12 entradas, na ordem acima, com principal preservado.
- Segunda execução de planejamento confirmou `changed=False`: atualização idempotente.
- **Smoke após a ativação:** execução padrão `hermes --ignore-rules --usage-file ... -z 2+2=?` retornou `4`, exit code 0. Relatório: `completed=true`, `provider=nous`, `model=stepfun/step-5-preview:free` (primeiro fallback), `api_calls=1`, `estimated_cost_usd=0.0` e `cost_status=estimated`; o modelo principal foi preservado na configuração.
- Não há teste de interrupção real forçada dos provedores em produção: a cadeia está instalada e os endpoints escolhidos foram testados separadamente, mas a transição de ponta a ponta foi verificada pelo contrato de configuração do Hermes, não por outage real.

## Política, recuperação e operação

O fallback principal do Hermes é `fallback_providers:` em `~/.hermes/config.yaml`; não confundir com o backend OpenCode ou com o pool de credenciais. Aumentar indiscriminadamente 80 entradas elevaria a latência de falhas e incluiria modelos de embeddings, imagens ou APIs obsoletas.

Para verificar: `hermes fallback list`. Para replanejar a partir de uma revisão do repositório, rode o módulo `infrastructure.pentium.atlas.hermes_fallback_rollout` usando `--manifest` com a configuração versionada; omita `--apply` para dry-run. A rotina salva um backup privado do YAML anterior antes de qualquer mudança. Não recomendo reverter o arquivo inteiro sem conferir modificações operacionais posteriores.

As chamadas NVIDIA são disponibilizadas como teste gratuito de prototipagem; verifique painel de consumo/quota antes de uso frequente. O serviço OpenCode por SSH, o modelo Hermes principal e o daemon Atlas foram preservados.
