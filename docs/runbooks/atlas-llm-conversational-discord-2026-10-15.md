# Atlas — fala natural via LLM e contexto de estado afetivo (2026-10-15)

## Contrato arquitetural

- **Atlas**: agente pessoal, proprietário do ciclo cognitivo, da observação, das decisões, da autorização e do gateway Discord.
- **Hermes**: mecanismo de inferência/modelos (“mentes”); não possui a identidade do agente principal nem seu canal Discord.
- **LLM**: redige mensagens conversacionais com base em evidências; sua saída é **dado não confiável** e não autoriza execução.
- **Motor afetivo**: métricas **simuladas**, interpretadas somente para contexto/tom, sem atribuir sentimentos humanos, consciência, dor ou necessidades.
- **Gateway próprio**: `atlas-discord.service` transmite as mensagens validadas.

## Fluxo da conversa recebida

```text
Discord (mensagem humana)
  -> Atlas Discord Gateway: allowlist + ChatInbox
  -> CognitiveDaemon: snapshot de observação + estado afetivo
     + resumo do grafo temporal (operational_graph_llm_context.py)
  -> ContextoCognitivoBuilder / LLMGateway
  -> HermesAdapter: modelo Nous + fallbacks configurados
  -> parser de saída estruturada + policy/capabilities
  -> dashboard-events.jsonl (resposta Atlas)
  -> Atlas Discord Gateway -> usuário
```

A conexão ao grafo é feita no `CognitiveDaemon` com `graph_context_loader`, injetado por `build_owner` para diálogos humanos **e** ativações autônomas. O resumo máximo contém medição atual e delta das seis métricas afetivas, contagem histórica de observações e agentes registrados (sem nomes ou texto privado). O grafo não contém comandos; `causality=unverified_temporal_association`.

**Deploy conservador**: o checkout do repositório e o daemon instalado diferem na política `CP-SEC-01`, `DelegationBridge` e executor local. Foram preservadas todas as regras do daemon em produção; somente cinco mudanças pontuais ligaram o contexto. Backup privado: `~/pentium-agent/atlas/runtime/cognitive_daemon_before_llm_graph_20261015.py`. Serviço reiniciado em 10:22:38 -03, com `ATLAS_COGNITIVE_DAEMON_READY`. Não substituir a versão instalada indiscriminadamente pelo checkout.

## Fluxo do alerta periódico já homologado

```text
atlas-hermes-adaptive.timer (aprox. 5 minutos)
  -> GET catálogos oficiais Nous / NVIDIA
  -> comparar contra política e estado anterior (deduplicação ~1h)
  -> coletar estado afetivo resumido e mudanças categóricas (sem payload bruto)
  -> Hermes one-shot: Nous / stepfun/step-5-preview:free
  -> validar JSON {message}, comprimentos, números de evidência, menções,
     alegações de custos/quotas/sensações reais e ausência de segredos
  -> discord-action-queue.jsonl: discord_send_alert + narrated_by=atlas_llm
  -> atlas-discord.service: mensagem redigida sem prefixo técnico
  -> canal de alertas configurado
```

- Sem nova decisão / resumo repetido: **sem chamada de inferência nem mensagem** até o intervalo de relatório.
- Inferência ausente, saída inválida ou alegações não verificadas: **não entregar o texto fixo antigo** nem avançar o registro de envio; próxima iteração tenta novamente.
- O serviço de checagem de modelos não concede capabilities à LLM. A chamada passa um JSON pequeno, com métricas simuladas sanitizadas, e `--ignore-rules`, sem segredos operacionais.
- Falta de cota conhecida NÃO implica disponibilidade infinita; API NVIDIA gratuita de prototipagem permanece sujeita às regras de uso.
- Um evento de `discord_send_alert` sem `narrated_by=atlas_llm` conserva o prefixo `[ALERTA ATLAS]`, pois não há prova de narração. **Outras fontes legadas ainda podem usar esse formato.**

## Evidências reais, host pentium

- Primeira inferência `hermes -p atlas`: excedeu 80 segundos. O sistema não publicou o texto fixo, conforme política de segurança.
- Corrigida a chamada para inferência explícita `--provider nous --model stepfun/step-5-preview:free --reasoning minimal --ignore-rules`: resposta JSON conversacional em 13 segundos, com números preservados.
- Uma nova execução `--apply` publicou `ATLAS_DISCORD_QUEUED True`.
- Após ativação do novo gateway, outra execução controlada publicou `ATLAS_DISCORD_QUEUED True` e o diário `atlas-discord.service` registrou `ATLAS_DISCORD_ALERT_DELIVERED` às 10:28:36 -03.
- `atlas-cognitive.service`, `atlas-discord.service` e `atlas-observation.service`: **active** após os deploys.
- A suíte regressiva dos novos módulos, daemon e gateway passou com **56 testes no Windows** e **18 testes isolados no Linux** para os módulos de notificação e fallback. O staging Linux é parcial e não inclui todas as dependências do daemon cognitivo; para ele, foram feitos testes Windows, pré-compilação da versão de produção e reinício real com `ATLAS_COGNITIVE_DAEMON_READY`. Não alegar homologação Linux integral da suíte cognitiva.
- Backups locais realizados também para `discord_gateway.py` em `~/pentium-agent/atlas/runtime/discord_gateway_before_llm_natural_20261015.py`.

## Limitações e próximos gates

1. **Alertas de emergência do watchdog ainda podem ser determinísticos**, para preservar aviso imediato se a LLM ficar indisponível. O fluxo de alertas de modelos está narrado. Outros fluxos `discord_send_alert` legados ainda precisam migrar para eventos tipados + narrador; não afirmar que 100% das saídas Discord passam por LLM.
2. A conversação bidirecional já tem ligação programada ao `LLMGateway` e ao novo grafo. Este checkpoint validou startup do daemon, mas não simulou uma nova mensagem humana real depois do restart; validar com interação do operador e recibo de envio.
3. Os rastros de uso/resposta Hermes devem ser associados a `model`, `provider`, `latency`, `decision_id`, `notification_id` e ao grafo operacional para auditoria longitudinal. `narrated_by` hoje garante a decisão do produtor, mas não é prova criptográfica.
4. Erros/atrasos e notificações devem ter dead-letter queue, recibo Discord (ID remoto) e recuperação garantida; o cursor atual pode avançar em erro do consumidor.
5. Perspectiva de longo prazo: assistente disponível para conversas espontâneas governadas, não mensagens compulsivas; limites de frequência, horário e prioridade de incidentes devem prevalecer sobre estilo afetivo.
