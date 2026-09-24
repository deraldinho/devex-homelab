# Documentação — DevEx HomeLab

A documentação é organizada por responsabilidade e funciona como parte da fonte de verdade operacional.

## Hierarquia

1. [GDD Mestre](GDD.md) — visão, experiência e regras globais do produto.
2. [Design arquitetural](architecture/devex-homelab-design.md) e [Atlas Local Intelligence](architecture/atlas-local-intelligence-design.md) — arquitetura dos nós, runners, simulação e inteligência cognitiva.
3. [PRD-0001 — Foundation](prd/PRD-0001-foundation.md) — requisitos e critérios de aceite da primeira iniciativa.
4. [Implementation Plan da Foundation](implementation/2026-09-02-foundation-plan.md) — sequência executável da foundation.
5. [Foundation CI Bootstrap](implementation/2026-09-02-foundation-ci-bootstrap.md) — gate transitório antes do runner físico.
6. [UML — Deployment e entrega](uml/deployment.md) — deployment e sequência de promoção.
7. [Políticas de governança](governance/policies.md) — branches, PRs, checkpoints, segurança e emergência.
8. [As-built baseline](as-built/2026-09-02-baseline.md), [As-built de estabilização](as-built/2026-09-19-homelab-stabilization.md) e [As-built Atlas 3.0](as-built/2026-09-20-atlas-3-0-affective-consciousness-l2j.md) — estado físico comprovado nos equipamentos.
9. [Runbook L2jToren](runbooks/l2jtoren-observability-operations.md) e [Runbook Discord/GitHub](runbooks/atlas-multisource-github-discord.md) — procedimentos operacionais.
10. [Release Notes v0.2.0](releases/v0.2.0.md) — notas de versão estável.

## Slice #14 — Simulação Docker da x99

- [PRD-0014](prd/PRD-0014-x99-docker-simulation.md) — requisitos da simulação local;
- [Implementation Design](implementation/2026-09-02-x99-docker-simulation-design.md) — contratos e decisões técnicas;
- [UML da simulação](uml/x99-docker-simulation.md) — componentes, deployment e sequência de certificação;
- [As-built da simulação](as-built/2026-09-02-x99-docker-simulation.md) — estado efetivamente validado;
- [`dev/simulation/README.md`](../dev/simulation/README.md) — execução operacional da stack.

## Regra de manutenção

Documentação de design descreve o estado desejado. Documentação `as-built` registra o estado efetivamente comprovado nos equipamentos. Quando divergem, a divergência é tratada como trabalho de reconciliação e não deve ser ocultada.
