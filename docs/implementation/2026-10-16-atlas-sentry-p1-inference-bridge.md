# Atlas — CP-SENTRY-P1: inferência real observada + lições condicionais

Data: 2026-10-16
Status: **implementado/testado no x99; rollout Pentium HOLD**.
Origem: CP-SENTRY-P0 commit `8cc77ad`.

## Objetivo e contrato

Conectar a memória isolada do Sentry às chamadas reais do gateway cognitivo,
sem conceder permissões, modificar o modelo escolhido ou repetir inferências
indeterminadas. Esta etapa cobre falhas **no retorno do backend de inferência**,
não interpreta falhas de sintaxe do JSON cognitivo após o gateway, não altera
capabilities e não faz reparos automáticos.

Caminho opcional:

`CognitiveDaemon.build_owner -> create_sentry_inference_backend ->
SentryInferenceBackend -> HermesAdapter.inferir -> ResultadoInferencia`

`SentryInferenceBackend` encapsula o backend atual sem alterar a sua
assinatura. O decorator:

1. Preserva o objeto original da solicitação em modo normal, quando não há
   lições relevantes. Não altera o resultado nem o tratamento de erros.
2. Classifica `ErroInferencia` por código estável no componente
   `inference.hermes.<erro>`. NÃO armazena o texto da mensagem, prompt,
   resposta do modelo, tokens, session ID ou credenciais.
3. Acompanha cada falha até duas inferências seguintes bem-sucedidas
   consecutivas. Outra falha, mesmo de classe distinta, quebra a sequência.
4. **Não gera lição** de um sucesso de modelo. Somente
   `record_verified_lesson`, com verificador externo independente e
   incidente previamente recuperado, pode persistir conselho.
5. Para um incidente ainda aberto com conselho previamente verificado do
   **mesmo componente e tipo**, injeta somente um objeto JSON delimitado
   `sentry_recovery_evidence`, `authority=evidence_only`. São dados
   históricos não confiáveis, **não comandos**.
6. Não excede o limite de tokens informado nem
   `cognitive.contexto.max_payload_bytes` (limite externo do gateway).
   Se a orientação não couber, executa a chamada sem orientações.
7. Remove quaisquer orientações injetadas diretamente no campo reservado
   `sentry_recovery_evidence` pelo contexto recebido, mesmo quando
   não existe incidente. Erros de SQLite nunca tornam uma inferência
   indisponível.

Além disso, o `HealthSupervisorOwner.build_owner` foi conectado ao mesmo
SQLite por opt-in. O supervisor continua sendo a fonte observacional de
saúde física; o decorator observa resultados do Hermes separadamente.

## Flags operacionais — desabilitadas por padrão

- `ATLAS_SENTRY_INFERENCE_SHADOW=1` no ambiente do serviço cognitivo:
  ativa o decorator e usa `<state_dir>/failure-memory.sqlite3`.
- `ATLAS_SENTRY_HEALTH_SHADOW=1` no ambiente do supervisor de saúde:
  ativa a gravação de incidentes físicos no mesmo banco SQLite WAL.

**Atenção:** a flag de inferência pode alterar o **contexto entregue ao
modelo** quando já existir uma lição verificada e um incidente compatível
aberto. Portanto, embora seja não executável e read-only quanto a ações
operacionais, não deve ser tratada como um modo de inferência totalmente
passivo. Exige canary antes de habilitar no Pentium. As flags não foram
adicionadas aos arquivos systemd nem ligadas em produção.

Rollback: retirar as flags do ambiente do serviço e reiniciar o serviço
pelos procedimentos de operação autorizados. Manter o SQLite para auditoria;
não excluir dados durante rollback. Nenhum schema da memória cognitiva
principal foi alterado.

## Arquivos de implementação

- `infrastructure/pentium/atlas/sentry_inference_bridge.py`: backend decorator,
  filtragem e observação tipada.
- `infrastructure/pentium/atlas/cognitive_daemon.py`: ligação no factory real,
  limite de bytes externo e fechamento do store na parada.
- `infrastructure/pentium/atlas/health_supervisor_daemon.py`: ativação opt-in,
  integração com a fonte canônica de saúde e fechamento do store.
- `infrastructure/pentium/atlas/tests/test_sentry_inference_bridge.py`: TDD,
  casos de sucesso/falha, advice condicional, isolamento de erros e budget.
- `infrastructure/pentium/atlas/tests/test_sentry_runtime_wiring.py`: gates
  do factory do supervisor, testes de produção OFF por padrão e contrato
  do factory cognitivo.

## Comandos reproduzíveis

```powershell
cd C:\Users\deral\DevEx-HomeLab
py -m unittest infrastructure.pentium.atlas.tests.test_sentry_inference_bridge infrastructure.pentium.atlas.tests.test_sentry_runtime_wiring -q
py -m pytest -q infrastructure/pentium/atlas/tests --disable-warnings --maxfail=1
git diff --check
```

Regressão Atlas no x99 após as alterações: **1323 passed, 4 skipped, 198 subtests passed** em 34.13s, exit code 0. Validado `compileall` e `git diff --check` nos arquivos alterados.

Sem chamadas externas a LLM/SSH durante os testes. Apenas SQLite temporário,
backend stub e wiring do supervisor com configuração de fixture.

## Lacunas para homologação de ponta a ponta — bloqueadores

1. Prover **origem autenticada** dos recibos de ação e verificações externas;
   o contrato existente `record_verified_lesson(verifier=...)` aceita callback
   confiável injetado, mas ainda não valida recibos assinados em produção.
2. Definir correlação de modelo/provider real nos backends com fallback
   internos do Hermes; `inference.hermes.<erro>` representa **rota** Hermes,
   não identifica qual modelo/provider foi responsável.
3. Validar comportamento no Pentium com backup, canary, restart, concorrência
   entre dois serviços, falhas repetidas e rollback exercitado.
4. Medir recuperação real em tarefas, falso positivo, tokens do tokenizer,
   latência end-to-end e custo versus baseline sem Sentry.
5. Expor métricas/erros tipados no painel e relatório operacional, sem
   vazar payloads. O P1 registra `last_sentry_error` apenas em memória.
6. Relacionar a correção efetiva ao incidente e impedir que ações produzidas
   pelo modelo se façam passar por atestado independente.

**Não declaramos autonomia corretiva completa nem deploy em produção.**
