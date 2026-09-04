# Documentação — DevEx HomeLab

A documentação é organizada por responsabilidade e funciona como parte da fonte de verdade operacional.

## Hierarquia

1. [GDD Mestre](GDD.md) — visão, experiência e regras globais do produto.
2. [Design arquitetural](architecture/devex-homelab-design.md) — arquitetura dos nós, runners, simulação e deploy.
3. [PRD-0001 — Foundation](prd/PRD-0001-foundation.md) — requisitos e critérios de aceite da primeira iniciativa.
4. [Implementation Plan](implementation/2026-09-02-foundation-plan.md) — sequência executável da foundation.
5. [Foundation CI Bootstrap](implementation/2026-09-02-foundation-ci-bootstrap.md) — gate transitório antes do runner físico.
6. [UML — Deployment e entrega](uml/deployment.md) — deployment e sequência de promoção.
7. [Políticas de governança](governance/policies.md) — branches, PRs, checkpoints, segurança e emergência.
8. [As-built baseline](as-built/2026-09-02-baseline.md) — estado observado que iniciou o projeto.

## Regra de manutenção

Documentação de design descreve o estado desejado. Documentação `as-built` registra o estado efetivamente comprovado nos equipamentos. Quando divergem, a divergência é tratada como trabalho de reconciliação e não deve ser ocultada.
