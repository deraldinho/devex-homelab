# A2 — Entidades, Vínculos e Expectativas — Plano de Implementação

> **Para execução com agentes:** SUB-SKILL OBRIGATÓRIA: usar `superpowers:subagent-driven-development` ou `superpowers:executing-plans`. Cada tarefa de código segue RED → GREEN e termina em commit próprio.

**Objetivo:** implementar o contexto afetivo determinístico que identifica entidades do Home Lab, mantém vínculos, exige incorporação explícita de membros, registra expectativas planejadas e conserva experiência operacional bounded para uso futuro pela A3.

**Arquitetura:** A2 fica acima do núcleo afetivo A1 e abaixo da futura percepção/correlação A3. Ela não interpreta `Stimulus`, não decide saúde técnica, não cria causalidade e não escolhe foco ou emoção; fornece contratos e estado contextual pequenos, persistentes e determinísticos.

**Stack técnica:** Python stdlib-first, `dataclasses`, `enum`, `datetime`, `collections.deque`, `json`, `pathlib`, `os`, `unittest`; sem dependência externa.

**Especificação:** `docs/implementation/2026-09-04-atlas-motor-estado-afetivo-design.md`

## Restrições globais

- Base exata: A1 certificada no SHA `1f78fd1c4d0b0e789927c2633c2da9eb5d7e4f1c`.
- Branch: `atlas/issue-20-entidades-vinculos-expectativas`.
- O estado técnico continua autoritativo e nunca é reclassificado pela A2.
- LLM, áudio, rede, SSH, Tailscale, firewall, systemd e ações de controle permanecem fora de escopo.
- Valores afetivos permanecem limitados a `0.0..1.0`; IDs e timestamps precisam ser válidos e determinísticos.
- Membros só produzem contexto afetivo de pertencimento depois de incorporação explícita.
- Histórico de experiência é bounded por capacidade configurada no construtor, sem fila ilimitada.
- Nenhuma taxa de aprendizagem, importância ou proximidade será inventada: evolução de vínculo recebe deltas explícitos e apenas aplica limites.

## Estrutura de arquivos

- Criar `infrastructure/pentium/atlas/modelo_contexto_afetivo.py`: tipos de entidade, vínculo, expectativa e experiência.
- Criar `infrastructure/pentium/atlas/contexto_afetivo.py`: cadastro, incorporação, agenda e histórico bounded.
- Criar `infrastructure/pentium/atlas/persistencia_contexto_afetivo.py`: snapshot atômico versionado e restauração segura.
- Criar testes dedicados sob `infrastructure/pentium/atlas/tests/`.
- Modificar `infrastructure/pentium/atlas/install-user.sh` e `.github/workflows/foundation-ci.yml` apenas depois dos contratos GREEN.

### Tarefa 1: Contratos de entidade e vínculo

**Produz:** `TipoEntidadeAfetiva`, `EntidadeAfetiva`, `VinculoAfetivo`.

- [ ] Escrever `test_modelo_contexto_afetivo.py` cobrindo categorias canônicas, validação de IDs, limites de vínculo e evolução bounded sem alterar campos manuais.
- [ ] Rodar o teste isolado e confirmar RED por módulo ausente.
- [ ] Implementar o mínimo em `modelo_contexto_afetivo.py`.
- [ ] Rodar teste isolado + suíte Atlas completa e confirmar GREEN.
- [ ] Commit: `feat(atlas): adicionar entidades e vinculos afetivos A2`.

### Tarefa 2: Expectativas e experiência operacional

**Produz:** `TipoExpectativa`, `EstadoExpectativa`, `Expectativa`, `TipoExperienciaOperacional`, `ExperienciaOperacional`.

- [ ] Acrescentar testes RED para manutenção planejada, retorno esperado, atraso determinístico, conclusão/cancelamento e registros operacionais imutáveis.
- [ ] Confirmar RED porque os contratos ainda não existem.
- [ ] Implementar contratos sem observar rede ou saúde técnica.
- [ ] Confirmar GREEN isolado + suíte completa.
- [ ] Commit: `feat(atlas): adicionar expectativas e experiencia operacional A2`.

### Tarefa 3: Registro contextual e reincidência bounded

**Produz:** `ContextoAfetivo`, cadastro de entidades, incorporação explícita, agenda de expectativas e histórico de experiência com capacidade fixa.

- [ ] Escrever `test_contexto_afetivo.py` cobrindo membro não incorporado, incorporação idempotente, vínculo obrigatório, expectativa ativa/atrasada, deque bounded e fator de reincidência limitado.
- [ ] Confirmar RED.
- [ ] Implementar `contexto_afetivo.py`; `fator_reincidencia()` recebe janela e limite explicitamente, sem threshold global inventado.
- [ ] Confirmar GREEN isolado + suíte completa.
- [ ] Commit: `feat(atlas): implementar contexto afetivo A2`.

### Tarefa 4: Persistência e retomada do contexto

**Produz:** `RepositorioContextoAfetivo` com esquema `1`, escrita temporária + `os.replace`, carga validada e fallback explícito para contexto vazio em arquivo ausente.

- [ ] Escrever `test_persistencia_contexto_afetivo.py` cobrindo round-trip, ausência, corrupção, esquema incompatível e respeito ao limite do histórico.
- [ ] Confirmar RED.
- [ ] Implementar persistência sem alterar o snapshot A1 de `EstadoAfetivo`.
- [ ] Confirmar GREEN isolado + suíte completa.
- [ ] Commit: `feat(atlas): persistir contexto afetivo A2`.

### Tarefa 5: Empacotamento e gate A2

- [ ] Escrever `test_a2_empacotamento.py` primeiro, exigindo novos módulos no installer e marker `DEVEX_HOMELAB_ATLAS_AFETIVO_A2_PASS` no CI.
- [ ] Confirmar RED.
- [ ] Atualizar `install-user.sh` e `foundation-ci.yml`, incluindo `py_compile` dos módulos A2.
- [ ] Confirmar GREEN da suíte completa, `py_compile`, `bash -n` e `git diff --check`.
- [ ] Commit: `ci(atlas): certificar contexto afetivo A2`.

## Gate de conclusão

A2 só será considerada concluída quando o HEAD exato possuir suíte Atlas completa GREEN, checks locais de sintaxe/empacotamento GREEN e GitHub Foundation CI GREEN. A PR deve permanecer Draft e empilhada sobre A1; A3 só começa depois desse gate.
