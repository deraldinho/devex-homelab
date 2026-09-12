# Atlas Personal Workspace + Self Work + Cognitive Economy v1

## Objetivo
Dar ao Atlas um universo próprio, persistente e auditável para criar notas, rascunhos, ideias, projetos e artefatos por iniciativa própria, sem conceder acesso genérico ao filesystem, shell, execução de código ou rede. O subsistema deve ampliar autonomia sem ampliar proporcionalmente risco operacional ou consumo de tokens.

## Princípios
1. Workspace não é Memory M2. Memory lembra; Workspace produz; Continuous Intent acompanha; Self Work decide trabalhar.
2. Toda operação de arquivo passa por um Workspace Broker determinístico. Hermes nunca recebe filesystem genérico.
3. A raiz do workspace é a única fronteira gravável pelo subsistema.
4. Nenhum arquivo criado pelo Atlas é executável pelo runtime.
5. Operações destrutivas permanentes exigem confirmação humana; exclusão autônoma é somente para lixeira recuperável.
6. Local first, cache second, retrieval third, LLM last.
7. Nenhum contexto é enviado ao Hermes apenas porque existe; entra somente se for necessário para a decisão atual.

## Estrutura do workspace
Raiz física sugerida: `~/pentium-agent/atlas-workspace/`.

- `inbox/`: itens pendentes de triagem.
- `notes/`: notas deliberadas.
- `journal/`: diário operacional/narrativo reduzido.
- `ideas/`: hipóteses e ideias ainda imaturas.
- `projects/`: trabalhos Self Work estruturados.
- `scratch/`: material temporário.
- `artifacts/`: resultados prontos para apresentar ao usuário.
- `archive/`: material encerrado preservado.
- `.trash/`: exclusões reversíveis.
- `.system/`: manifestos, índice, provenance, locks, quotas e health.

## Fronteira de segurança
O broker recebe caminhos lógicos (`area`, `relative_path`) e nunca aceita caminhos absolutos. Deve rejeitar `..`, normalizações que escapem da raiz, symlinks, hardlinks suspeitos, dispositivos, sockets, FIFOs e extensões não permitidas. Após canonicalização, o caminho resolvido deve continuar contido na raiz real do workspace.

Permissões padrão: diretórios `0700`, arquivos `0600`, `umask 0077`.

Tipos v1 permitidos: `.md`, `.txt`, `.json`, `.jsonl`, `.csv`. Arquivos executáveis ou interpretáveis operacionais (`.sh`, `.py`, `.js`, `.service`, binários etc.) não podem ser criados como arquivos autônomos. Código pode existir apenas como texto dentro de documento permitido.

Não existem capabilities `filesystem_*`, `shell`, `execute_file`, `run_script` ou equivalentes.

## Constitution / Boundary Manifest
Configuração versionada deve definir, no mínimo:
- `workspace_version=1`
- quota total inicial: 128 MiB
- tamanho máximo por arquivo: 1 MiB
- máximo inicial: 2048 arquivos
- Self Work habilitado
- criação/edição própria habilitada
- trash habilitado
- purge automático desabilitado
- execução desabilitada
- paths externos desabilitados
- symlinks desabilitados
- network-from-workspace desabilitada

A política deve ser aplicada por código, não por prompt.

## Capabilities
READ/AUTO:
- `workspace_status`
- `workspace_list`
- `workspace_read`
- `workspace_search`

CONTROL/AUTO, estritamente dentro da raiz e dos budgets:
- `workspace_create_note`
- `workspace_write`
- `workspace_append`
- `workspace_mkdir`
- `workspace_move`
- `workspace_archive`
- `workspace_trash`
- `workspace_restore`

DESTRUCTIVE/CONFIRM:
- `workspace_purge`

CONTROL/CONFIRM:
- `workspace_export`

Cada execução produz evento de auditoria com intent, capability, target lógico, resultado, bytes e fingerprint; conteúdo sensível completo não deve ser duplicado desnecessariamente nos logs.

## Self Work Runtime
Nova origem de intenção: `SELF_WORK_INTENT`, distinta de `USER_INTENT` e `OBSERVATION_INTENT`.

Estados: `CANDIDATE -> ACTIVE -> WORKING -> REVIEWING -> COMPLETED`, com saídas `PAUSED`, `ABANDONED`, `EXPIRED`, `BLOCKED`.

Preempção humana: interação do usuário pausa Self Work imediatamente; após a interação, o runtime só retoma se a intenção continuar válida e dentro do budget.

Budget inicial:
- máximo 1 Self Work concorrente;
- máximo 20 operações de workspace por janela de 10 minutos;
- ciclo máximo de 5 minutos;
- no máximo 1 inferência inicial, 1 inferência adicional se houver informação material nova e 1 inferência final opcional;
- operações locais determinísticas entre inferências não consomem chamadas LLM.

Self Work não autoriza novas capabilities de infraestrutura. Ele usa somente as policies já existentes ou o novo conjunto de workspace.

## Provenance
Cada artefato mantém metadata com pelo menos: path lógico, `created_by=atlas`, created/updated timestamps, reason (`human`, `observation`, `self_work`), source_intent, source_episode/stimulus quando houver, revision, content hash e policy version.

Deve ser possível explicar por que um arquivo existe e qual evidência/intenção o originou sem reexecutar o LLM.

## Lixeira e retenção
`workspace_trash` é AUTO e move atomicamente para `.trash/`, preservando metadata original. Purge permanente é desabilitado para autonomia v1. Retenção sugerida de 30 dias serve apenas como sinal para revisão; não apaga automaticamente.

## Cognitive Economy
### Roteamento
Antes do Hermes, o Cognitive Router classifica o trabalho em:
1. deterministic path;
2. persistent/local cache;
3. local retrieval/index;
4. compact-context LLM.

Metadados, quota, listagem, busca lexical, hashes, verificação de escrita, moves, archive/trash/restore e estado estruturado devem ser resolvidos sem LLM.

### Workspace Index
Usar SQLite local, preferencialmente FTS5 quando disponível, com fallback determinístico caso FTS5 não exista. Indexar path, título, tags, resumo, palavras-chave, content hash, timestamps, relationships e fragmentos pesquisáveis. O índice não concede novos paths ao runtime.

### Progressive Retrieval
Ordem obrigatória: metadata -> digest -> snippets -> arquivo completo. Só sobe de nível quando a evidência anterior é insuficiente. Arquivo completo é exceção, não padrão.

### Context Packs
O ContextPackBuilder monta contexto por necessidade e aplica hard ceilings. Valores iniciais sugeridos:
- normal: alvo 3000 tokens;
- complexo: teto 6000;
- emergência: teto 8000.

O teto não é objetivo de uso. Prioridade de inclusão: intenção atual, delta de observação, memória relevante, snippets do workspace, conversa recente necessária e policy/state mínimo.

### Delta Context
Snapshots repetidos são representados como mudanças materiais desde o fingerprint anterior. Estado invariável não é reenviado ao LLM.

### Persistent Context Cache
Chave content-addressed composta por hashes de conteúdo relevante, query/intent, model id e policy version. Cache deve sobreviver restart, ter TTL/limite bounded e invalidar por mudança material ou policy/model version.

### Incremental Digests
Alterações pequenas atualizam digests usando old digest + changed chunk + metadata. Reprocessamento integral só ocorre quando o digest não é confiável, a estrutura muda materialmente ou a política exige reconstrução.

### No-op cognitivo
Se não há mudança material, interação humana, deadline, mudança afetiva relevante, Self Work pendente ou condição terminal, retornar `NO_INFERENCE_REQUIRED` e não chamar Hermes.

### Cognitive Batching
Tarefas de baixa urgência podem ser agregadas em uma única reflexão bounded, respeitando causalidade, freshness e prioridade. Incidentes e interação humana nunca aguardam batching.

## Token Budget Governor
Orçamento adaptativo, não limite diário rígido. Prioridades: Human > Critical Incident/Recovery > Observation material > Self Work > Periodic Reflection.

Estados: `NORMAL`, `CONSERVATIVE`, `RESTRICTED`, `HUMAN_ONLY`.
- `NORMAL`: política padrão.
- `CONSERVATIVE`: contextos menores, mais cache/batching.
- `RESTRICTED`: Self Work LLM reduzido/suspenso; rotas determinísticas continuam.
- `HUMAN_ONLY`: apenas interação humana e incidentes críticos podem consumir nova inferência; observação, indexação e capabilities determinísticas permanecem ativas.

O governor deve contabilizar input/output tokens quando o backend fornecer usage e usar estimativa conservadora quando não fornecer. Falha na contabilização não pode liberar orçamento ilimitado.

## Observabilidade
Dashboard/runtime health deve expor sem conteúdo privado completo:
- workspace health, quota e file count;
- Self Work state e projeto/intent atual;
- operações workspace e bloqueios;
- LLM calls, avoided calls, deterministic routes;
- cache hit/miss/eviction;
- input/output tokens observados/estimados;
- consumo por categoria (human, incident, observation, self_work, reflection);
- estado atual do Token Budget Governor;
- média de snippets/context bytes por retrieval.

## Fail-closed e degradação
Falha no índice não libera leitura irrestrita: broker continua impondo path/policy e pode operar sem search. Falha no cache apenas causa miss. Falha de metadata/provenance em operação mutável deve abortar a mutação ou realizar rollback seguro. Quota cheia bloqueia novas escritas não críticas. Workspace indisponível não derruba Observation/Cognitive/Dashboard; Self Work entra em `BLOCKED`/degraded.

## Integração
O subsistema conecta-se a `CapabilityRegistry`, `PolicyCapabilities`, `ActionPlanner/Executor`, `ContinuousIntent`, `CognitiveDaemon`, observability/dashboard e ao cache/memory retrieval existente. Não substitui Memory M2 e não altera os limites atuais de autonomia de infraestrutura.

A ativação deve ocorrer em slice/PR própria, separada da ativação de Voice.

## Gates de aceitação
1. Path traversal, symlink escape, absolute paths e tipos proibidos falham em testes adversariais.
2. Quota, max file, max files e budgets são enforceados deterministicamente.
3. Trash/restore preservam provenance; purge exige confirmação e está desabilitado para AUTO.
4. Self Work é preemptado por interação humana e retoma apenas se ainda válido.
5. Operações determinísticas demonstram zero chamadas ao LLM.
6. Retrieval progressivo respeita ceilings e nunca injeta workspace inteiro por padrão.
7. Cache persistente invalida corretamente por conteúdo/policy/model.
8. `NO_INFERENCE_REQUIRED` evita inferência em estado materialmente idêntico.
9. Governor reduz Self Work antes de degradar interação humana.
10. Observabilidade mostra custos/evitações sem vazar conteúdo integral.
11. Testes Atlas completos e Dashboard completos GREEN no exact HEAD.
12. Deploy físico somente após CI all-GREEN; smoke prova isolamento, persistência, restart e estabilidade dos serviços existentes.

## Fora de escopo v1
Execução de código criado no workspace, shell, acesso arbitrário ao host, network tools a partir do workspace, escrita em Git/repositórios, purge autônomo, compartilhamento automático externo, multi-agent shared workspace e alteração autônoma da própria Constitution.
