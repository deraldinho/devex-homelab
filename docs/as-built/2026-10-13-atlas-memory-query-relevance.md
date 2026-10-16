# Atlas CP-MEM-02 — Memória recuperada por intenção humana

**Data:** 2026-10-13 · **Estado:** código local e testes GREEN; **deploy no Pentium HOLD**.

## Problema confirmado por TDD
O fluxo `ReactionLoopCognitivo.processar()` chamava `MemoryRetriever.retrieve(query_terms=(fingerprint, motivo.value))`. Em interações humanas, `fingerprint` pode ser um identificador opaco de estímulo e não contém os termos da pergunta. A busca no índice de memórias e no workspace ignorava, então, o que o operador havia perguntado.

Teste RED `test_memoria_recupera_termos_da_mensagem_humana_em_vez_do_fingerprint` exibiu:
```
AssertionError: 'backup do Pentium' not found in 'random-stimulus-12345'
```
Log original: `.atlas/opencode/tmp/cp-mem02-red.log`.

## Implementação
- Em `infrastructure/pentium/atlas/reaction_loop_cognitivo.py`, para `INTERACAO_HUMANA`, o recuperador privilegia `mensagem_usuario`, quando uma string não vazia.
- Caso ausente, procura nos últimos 16 `mudancas_recentes` apenas payload textual sob fontes `human.*`. Logs, ferramentas e telemetria não são usados como mensagem do operador.
- A consulta é limitada a 512 caracteres e permanece no escopo do `MemoryRetriever` e do `WorkspaceRetriever`. Para eventos não humanos, mantém `fingerprint` e motivo, preservando comportamento anterior.
- O módulo `HermesAdapter` agora inclui `memorias_relevantes` em bloco limitado explicitamente identificado como **evidência não confiável**, com conteúdo escapado e até 6 memórias × 320 caracteres. O contexto mantém o esquema estrito de oito campos de saída. **Não mudou seleção de modelo: provider=None continua delegando ao Hermes.**
- Os estados afetivos existentes chegam ao prompt (teste `test_affective_state_reaches_hermes_prompt`); isso comprova condicionamento de texto **em ambiente de teste**, não a reação de um LLM real.

## Evidências
- TDD RED: 1 falha esperada, 7 casos não selecionados.
- GREEN focado: `py -m pytest -q infrastructure/pentium/atlas/tests/test_reaction_loop_cognitivo.py infrastructure/pentium/atlas/tests/test_hermes_adapter.py infrastructure/pentium/atlas/tests/test_feature_inventory_contract.py` → **19 passed** na versão inicial; posteriormente, 2 testes adicionais de guarda no loop → **10 passed** para o módulo isolado.
- Regressão ampla já executada antes desta alteração teve **1152 passed, 25 skipped**, requer nova execução para certificação do HEAD.
- Não houve mudança de configuração, execução de Hermes real, instalação OpenCode no Pentium ou restart do Atlas.

## Próximas etapas
1. Regressão ampla + revisão independente.
2. Certificar memória recuperada de SQLite real em canal de teste sem vazamento de conteúdo privado.
3. Confirmar timeout e provider gratuito configurado no runtime Hermes, com cuidado para não forçar fornecedor pago.
4. Canary reversível no Pentium somente após comparação de código e validação de backup/rollback.
