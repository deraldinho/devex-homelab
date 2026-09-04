# Implementation Design — Foundation CI Bootstrap

Issue: #17

## Objetivo

Criar o primeiro gate GitHub Actions da foundation sem depender do runner físico que ainda será construído.

## Decisão

Durante o bootstrap, `foundation-ci.yml` usa `ubuntu-latest`. Esse runner hospedado é transitório e serve somente para validar o repositório antes da criação de `core-devex-homelab`.

O target definitivo permanece:

```text
core-devex-homelab
  labels: self-hosted, core, homelab, container, devex-homelab
```

A CI bootstrap não altera essa decisão arquitetural.

## Gate mínimo

A workflow valida:

- checkout do HEAD exato;
- `git diff --check` contra a base da PR;
- sintaxe de todos os scripts shell versionados;
- padrões básicos de secrets acidentais;
- ausência de placeholders de trabalho pendente;
- simulação Docker quando seus arquivos existirem na camada atual.
## Comportamento por camada

Na PR #15, `dev/simulation/` ainda não existe; a etapa registra `SIMULATION_NOT_PRESENT_ON_THIS_STACK_LAYER` e continua validando o baseline documental.

Depois que a PR #16 for restackada sobre a foundation atualizada, a mesma workflow detectará `dev/simulation/compose.yaml` e executará a certificação completa da simulação.

## Segurança

- `permissions: contents: read`;
- nenhum secret requerido;
- nenhum deploy;
- nenhum acesso a Core/Pentium;
- nenhum Docker socket do homelab;
- nenhum token de registro de runner.

## Promoção

Mesmo GREEN, esta CI não autoriza deploy físico. Ela apenas estabelece o baseline verificável necessário para seguir a cadeia de dependências.

A substituição pelo runner `core-devex-homelab` ocorre somente após Issues #5, #6, #7 e #8 e certificação no HEAD exato.