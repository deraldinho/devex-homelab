# PRD-0001 — Foundation do DevEx HomeLab

## Problema

O homelab já possui infraestrutura funcional, mas o estado foi construído incrementalmente e ainda não existia um repositório próprio que fosse a fonte de verdade operacional, com rastreabilidade de decisões, Issues, PRs, CI, checkpoints e as-built.

## Objetivo

Criar a foundation do DevEx HomeLab como projeto privado, reproduzível, container-first e governado por Git, estabelecendo o primeiro runner `core-devex-homelab` e preparando o padrão `core-<projectname>`.

## Usuário principal

Mantenedor do homelab e dos projetos hospedados nele.

## Requisitos funcionais

1. Repositório privado `deraldinho/devex-homelab`.
2. Working copy principal em `C:\Users\deral\DevEx-HomeLab`.
3. Inventário versionado de x99, core e pentium.
4. Simulação Docker local na x99.
5. Runner próprio do projeto no Core: `core-devex-homelab`.
6. CI executada nesse runner após sua certificação.
7. Control plane no Pentium capaz de observar runners por projeto.
8. Deploy controlado com aprovação para mudanças sensíveis.
9. Detecção de drift entre desired e observed state.
10. Rollback por versão/commit SHA.
11. Contrato explícito que mapeie componentes implantáveis para seus nós alvo.
12. Caminho manual controlado de recuperação usando os mesmos manifests aprovados.

## Requisitos não funcionais

- container-first;
- sem secrets versionados;
- Tailscale como caminho administrativo;
- x99 não pode ser dependência operacional obrigatória;
- jobs pesados devem executar no Core;
- HEAD exato precisa estar GREEN antes de promoção;
- mudanças permanentes devem possuir rastreabilidade;
- rollback deve usar versão previamente certificada.

## Fora de escopo

- Kubernetes;
- autoscaling automático de runners;
- segundo projeto real além de DevEx HomeLab e L2jToren;
- remoção imediata do runner legado da x99;
- auto-remediação agressiva de drift.

## Critérios de aceite

Os 12 itens da Definition of Done do design arquitetural devem estar comprovados por commits, CI, evidências e checkpoint da PR.
