# Atlas A4 — Foco e Emoção Derivada — Plano de Implementação

> Execução orientada por TDD, em branch/worktree isolada e empilhada sobre A3 certificada.

**Objetivo:** implementar foco principal/secundários bounded com histerese e rótulos emocionais derivados deterministicamente do `EstadoAfetivo` + contexto recente.

**Base certificada:** `30c735793e64466aa2426e29d322f8e8b2f9ff2b`.

**Arquitetura:** A4 consome estado afetivo e sinais contextuais já consolidados; não altera saúde técnica, percepção, correlação nem vínculo. Foco e emoção são projeções determinísticas e bounded, sem LLM.

## Restrições globais
- Um evento crítico relevante pode interromper o foco atual.
- Evento não crítico só substitui foco por margem configurada de histerese.
- Secundários têm capacidade fixa e ordenação determinística.
- Recuperação reduz prioridade sem apagar contexto instantaneamente.
- Emoção principal e nuances são derivadas; nunca viram nova fonte de verdade.
- `frustrado` exige reincidência + queda de confiança, não apenas estresse.
- Zero LLM, áudio, rede, diagnóstico ativo ou controle remoto.

## Tarefa 1 — Contratos de foco
- Criar `modelo_foco.py` com `AssuntoFoco`, `FocoAtencao` e política bounded/histerese.
- Testar validação, ordenação e capacidade de secundários.
- Commit: `feat(atlas): adicionar contratos de foco A4`.

## Tarefa 2 — Motor de foco
- Criar `motor_foco.py` para pontuação por gravidade, impacto afetivo, importância, novidade, urgência e recência.
- Crítico relevante interrompe; demais respeitam margem de histerese.
- Recuperação aplica redução de prioridade configurável.
- Commit: `feat(atlas): implementar foco com histerese A4`.

## Tarefa 3 — Emoção derivada
- Criar `emocao_derivada.py` com labels canônicos e nuances bounded.
- Derivar deterministicamente a partir de `EstadoAfetivo` + contexto resumido.
- Cobrir `calmo`, `atento`, `preocupado`, `alarmado`, `frustrado`, `aliviado`, `satisfeito`, `confiante`, `curioso`, `interessado`, `estressado`, `vigilante`.
- Commit: `feat(atlas): derivar emocoes deterministicas A4`.

## Tarefa 4 — Integração do contexto A4
- Criar `contexto_foco_emocao.py` para combinar foco atual, estado afetivo e contexto recente em snapshot pequeno.
- Manter tudo idempotente, determinístico e sem mutar A1/A2/A3.
- Commit: `feat(atlas): integrar foco e emocao derivada A4`.

## Tarefa 5 — Persistência, configuração e certificação
- Criar `config_foco_emocao.json` com capacidades/margens explícitas.
- Persistir snapshot A4 de forma atômica e versionada.
- Atualizar `install-user.sh` e `foundation-ci.yml` com gate `DEVEX_HOMELAB_ATLAS_AFETIVO_A4_PASS`.
- Rodar suíte completa, `py_compile`, JSON, `bash -n` e `git diff --check` contra A3.
- Criar PR Draft empilhada sobre `atlas/issue-20-percepcao-correlacao` e registrar `/checkpoint` só após CI GREEN no HEAD exato.
