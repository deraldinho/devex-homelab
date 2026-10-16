# Atlas — CP-SENTRY-P0: memória de falhas condicional e recuperação verificada

Data: **2026-10-16**
Origem: Sentry, Ji et al., arXiv **2610.02994**, publicado em 2026-10-02.
Estado: **STAGING LOCAL / PENTIUM DEPLOY HOLD**.

## Decisão técnica

Implementar os princípios do Sentry nativamente, sem importar código externo:
isolamento do playbook, observação de incidentes, recuperação condicional e
aprendizado somente após verificação independente. Não copiar os ganhos do
artigo como se fossem medições do Atlas.

Checkout inspecionado: `C:\Users\deral\DevEx-HomeLab`,
branch `atlas/v0.4.0-proprioception-autonomy`. A árvore já tinha numerosas
alterações/untracked de outros checkpoints; não houve reset, commit, branch
paralela, worktree nova ou deploy.

## Arquitetura executada

`infrastructure/pentium/atlas/failure_memory.py`

- SQLite dedicado `failure_incidents` + `failure_lessons`, independente de
  `memory_store.py`, `MemoryGraph` e memória de longa duração da LLM.
- Estados `open -> recovered`, transição condicionada a **duas leituras HEALTHY
  consecutivas** com evidência, após falha registrada. Uma falha intermediária,
  mesmo de categoria distinta, reinicia a contagem.
- Identidade tipada por componente e tipo de falha; idempotência por instante
  e persistência com high-watermark contra replays antigos.
- `record_verified_lesson()` aceita lições somente quando o incidente já
  está recovered, há `verification_refs` tipadas e um callback de validação
  externo confiável retornou exatamente `True`. Uma lição por incidente.
- `advice_for_incident()` recupera somente lições compatíveis com incidente
  **atualmente OPEN**; `max_items` e `max_bytes` estritos, TTL de 90 dias.
  Registros alterados maliciosamente no banco são revalidados no retrieval.
- Nenhum método executa reparos, chama LLM, ajusta permissões, autoriza
  capabilities, salva instruções na memória principal ou reinicia serviços.
- Dados retornados contêm `authority=evidence_only`; não são comandos.

`infrastructure/pentium/atlas/health_supervisor_daemon.py`

- `HealthSupervisorOwner(..., failure_memory=store)` é integração opt-in.
- Após publicar o snapshot canônico, encaminha observações ao novo store.
- Erro no store não derruba health supervision; classe da exceção fica em
  `owner.last_failure_memory_error`, sem expor strings de exceção nem payload.
- `build_owner()` e o processo principal continuam sem instanciar FailureMemory
  automaticamente; `config_health_supervisor.json` permanece inalterado.
  **Portanto o recurso ainda não está habilitado no Pentium.**

`infrastructure/pentium/atlas/tests/test_failure_memory.py`
`infrastructure/pentium/atlas/tests/test_failure_memory_supervisor.py`

- RED/GREEN: ausência do módulo e assinatura de injeção de supervisor; casos
  adversariais de tentativa de falso recovery, falha repetida, replay,
  timestamps fora de ordem, tipo de falha alterado, não-aprendizado sem
  verificação, callback que lança exceção, DB adulterado, credenciais em
  referências e limite de contexto.
- Os testes executam em SQLite temporário isolado. Um teste de symlink é
  ignorado se o token de Windows não possuir privilégios suficientes.

`tools/benchmark_failure_memory.py`

- Benchmark determinístico local (seed 261016), **200 eventos / 60 falhas
  injetadas = 30%**, quatro lições aprendidas em fixture com verificador
  simulado. Três braços: `none`, `all`, `conditional`.
- Arquivo bruto: `docs/implementation/2026-10-16-sentry-synthetic-benchmark.json`.

## Evidências quantitativas do benchmark sintético

| Política | Bytes de contexto (total) | Falhas com conselho | Conselhos indevidos em eventos sadios | p95 local |
|---|---:|---:|---:|---:|
| none | 0 | 0/60 | 0/140 | 0.0014 ms |
| all | 166400 | 60/60 | 140/140 | 0.0013 ms |
| conditional | 14994 | 60/60 | 0/140 | 0.3181 ms |

Comparação `all -> conditional`: 91% menos bytes agregados de contexto
de orientações no dataset sintético. O overhead p95 local inclui consulta
SQLite e serialização de dois itens no máximo. **Esse benchmark não executou
tarefas com modelos reais e NÃO demonstra melhora de sucesso, causalidade,
recuperação ou economia monetária de tokens de LLM.** Os tokens computados no
JSON são estimativa `ceil(bytes/4)`, não contagem do tokenizer real.

## Gates de aceitação

- Testes focados após hardening: **28 testes, OK, 1 skipped**.
- Regressão ampla final no x99: **1308 passed, 4 skipped, 198 subtests passed em 33.80s**; exit code 0. Skip adicional é o teste de symlink não disponível no token do Windows.
- Não há alteração no catálogo Hermes/OpenCode, configurações de provider,
  agentes em produção, permissões, schema da memória principal ou deploy.
- A implementação do registro de incidente e das lições é completa para
  **supervisor opt-in**. A integração ao ciclo real de inferência / executor
  continua bloqueada até comprovar proveniência autenticada e verificação
  de reparo via recibos assinados.

## Pendências para homologação operacional de ponta a ponta

1. **P0:** Verificador de recuperação independente baseado em recibos de
   execução assinados (não `lambda` ou autorrelato do agente).
2. **P0:** Integração autenticada com eventos Hermes/OpenCode (falhas de
   tool call, repetição, timeout, resposta inválida) e com caminho de
   solicitação contextual na LLM, sem inserir lições fora de incidentes.
3. **P0:** Testes adversariais de manipulação de DB/arquivos, leituras
   paralelas, concorrência multiprocessos e replay entre hosts.
4. **P1:** Benchmark com tarefas reais e intervenção controlada medindo
   taxa de recuperação, falsos diagnósticos, reincidência, tokens do
   tokenizer, latência total e custo.
5. **P1:** Canary opt-in no Pentium após backup, revisão independente,
   observabilidade, restauração testada, autorização de rollout e rollback.

Apenas após estes gates é legítimo marcar o Sentry do Atlas como
**100% homologado em produção**.
