# Implementation Design — Core Compute Node

Issue: #5
PRD: `docs/prd/PRD-0005-core-compute.md`

## Decisão

O Core é tratado como appliance de compute do HomeLab, não como workstation. O Git guarda contratos e verificadores; o host mantém apenas infraestrutura mínima e stacks persistentes em `~/homelab`.

## Desired state versionado

```text
infrastructure/core/
├── bootstrap/core-host-bootstrap.sh
├── verify/verify-core.sh
├── stacks/smoke/compose.yaml
├── tests/validate-repo.sh
└── CONTAINER_POLICY.md
```

`core-host-bootstrap.sh` é idempotente e só deve ser aplicado quando houver drift comprovado e aprovação para a mudança correspondente.

## Fronteira host × projeto

Host permitido:
- Ubuntu, Tailscale, SSH, Docker/Compose e ferramentas administrativas mínimas.

Host proibido:
- JDK, Ant, Node/npm, Codex e workspaces de código de projetos.

## Certificação

`infrastructure/core/tests/validate-repo.sh` valida o contrato no ambiente de desenvolvimento/CI:

- sintaxe dos scripts;
- Compose do smoke;
- execução real do container Alpine;
- ausência de toolchains de projeto no bootstrap;
- ausência de workspace `~/projects` no bootstrap;
- cleanup do smoke.

`infrastructure/core/verify/verify-core.sh` valida o host real:

- identidade/OS/Tailscale/timezone;
- Docker/Compose e daemon policy;
- sleep/lid policy;
- SSH hardening e wait-online;
- ausência de toolchains/workspace de projeto;
- smoke em `~/homelab/stacks/smoke`;
- zero failed units.

## Reconciliação

A sequência é `desired → observe → compare → reconcile only drift → certify`. Se `verify-core.sh` já passa, nenhuma aplicação física é necessária.

## Relação com runners

O container `github-runner-core` existente é observed state legado. Seu replacement não pertence à #5: #7 define a plataforma por projeto, #8 cria `core-devex-homelab` e #9 migra o L2jToren.
