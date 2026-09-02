# DevEx HomeLab Foundation Implementation Plan

> **For agentic workers:** executar tarefa por tarefa, com revisão e checkpoints. Código de produção novo deve usar TDD quando aplicável.

**Goal:** criar o repositório privado DevEx HomeLab, registrar o estado atual e colocar em operação o runner `core-devex-homelab` com CI containerizada e control plane por projeto.

**Architecture:** x99 é a working copy e ambiente de simulação; GitHub é a fonte de verdade; Core executa runners/containeres; Pentium observa e coordena deploys controlados. Cada projeto possui runner canônico `core-<projectname>`.

**Tech Stack:** GitHub, GitHub Actions Runner, Docker/Compose, Ubuntu 26.04, WSL2/Docker Desktop, Python 3, shell, Tailscale, SSH.

**Spec:** `docs/architecture/devex-homelab-design.md`

## Global Constraints

- repositório privado `deraldinho/devex-homelab`;
- working copy `C:\Users\deral\DevEx-HomeLab`;
- container-first;
- x99 não é dependência operacional;
- Tailscale para controle;
- nenhum secret versionado;
- deploy controlado;
- HEAD exato GREEN antes de promoção.

---

### Task 1 — Bootstrap do repositório e governança

**Deliverable:** repositório privado criado, `main` inicializado e primeira branch de foundation aberta.

- [x] Criar `deraldinho/devex-homelab` como private, com README inicial.
- [x] Clonar em `C:\Users\deral\DevEx-HomeLab`.
- [x] Confirmar remote `origin` e branch `main`.
- [x] Criar branch `foundation/issue-1-devex-homelab`.
- [x] Adicionar `.gitignore`, `.gitattributes`, documentação foundation, templates de Issue/PR e política de checkpoint.
- [x] Commit: `docs(foundation): establish DevEx HomeLab governance baseline`.

### Task 2 — Backlog inicial e rastreabilidade

**Deliverable:** Issues que representam o estado já construído e as próximas slices.

- [x] Criar Issue Foundation/Governance (#1).
- [x] Criar Issue Inventory/Baseline (#2).
- [x] Criar Issue Tailscale Management Mesh (#3).
- [x] Criar Issue Pentium Control Plane (#4).
- [x] Criar Issue Core Compute Node (#5).
- [x] Criar Issue Container-First Model (#6).
- [x] Criar Issue Runner Platform by Project (#7).
- [x] Criar Issue `core-devex-homelab` (#8).
- [x] Criar Issue `core-l2jtoren` migration (#9).
- [x] Criar Issues Monitoring (#10), Backup/DR (#11), Security (#12) e Capacity (#13).
- [x] Criar Issue x99 Docker Simulation (#14).
- [x] Registrar mapa e dependências em `docs/backlog/README.md`.

### Task 3 — Ambiente de simulação na x99 (#14)

**Deliverable:** Compose de desenvolvimento que valida a topologia lógica sem depender dos hosts reais.

- [ ] Criar `dev/simulation/compose.yaml` com `sim-core` e `sim-pentium` mínimos.
- [ ] Criar imagens base Ubuntu 26.04 para simulação.
- [ ] Montar o repo read-only onde apropriado e volumes temporários para estado de teste.
- [ ] Validar `docker compose config`.
- [ ] Subir o ambiente e validar health checks.
- [ ] Derrubar o ambiente sem deixar containers órfãos.

### Task 4 — Stack do runner core-devex-homelab

**Deliverable:** Dockerfile/Compose versionados e validados localmente.

- [ ] Criar `infrastructure/core/runners/devex-homelab/Dockerfile`.
- [ ] Criar `compose.yaml` com container `core-devex-homelab` e volume `core-devex-homelab-work`.
- [ ] Não persistir token de registro em arquivo versionado.
- [ ] Validar imagem localmente na x99.
- [ ] Adicionar smoke para runner listener e toolchain mínima.

### Task 5 — Registro do runner no Core

**Deliverable:** runner GitHub repo-level `core-devex-homelab` online no Core.

- [ ] Obter token temporário de registro.
- [ ] Implantar stack no Core via Tailscale/SSH.
- [ ] Registrar nome `core-devex-homelab`.
- [ ] Aplicar labels `core,homelab,container,devex-homelab` mais default labels.
- [ ] Confirmar `online=true`, `busy=false` via GitHub API.
- [ ] Confirmar container `running` e restart `unless-stopped`.

### Task 6 — CI e certificação

**Deliverable:** workflow GREEN no HEAD exato usando `core-devex-homelab`.

- [ ] Criar `.github/workflows/foundation-ci.yml`.
- [ ] Criar `.github/workflows/core-devex-homelab-certification.yml`.
- [ ] Selecionar `[self-hosted, core, homelab, container, devex-homelab]`.
- [ ] Validar runner name, workspace, Docker, Python, Git e Compose.
- [ ] Executar smoke de container.
- [ ] Registrar evidência `DEVEX_HOMELAB_RUNNER_CERTIFICATION_PASS`.

### Task 7 — Pentium control plane por projeto (TDD)

**Deliverable:** Pentium consulta runner por slug sem shell arbitrário.

- [ ] Escrever teste RED para `core.runner.project.status(project)`.
- [ ] Validar slugs contra allowlist/regex estrita.
- [ ] Mapear `devex-homelab -> core-devex-homelab` e `l2jtoren -> core-l2jtoren/core` durante transição.
- [ ] Implementar consulta GitHub API.
- [ ] Executar teste GREEN e `py_compile`.
- [ ] Reiniciar serviço e validar chamada direta + job enfileirado.

### Task 8 — PR, checkpoint e as-built

**Deliverable:** foundation rastreável e pronta para review.

- [ ] Abrir Draft PR vinculada à Issue #1.
- [ ] Confirmar HEAD exato e changed files.
- [ ] Aguardar/validar todos os checks obrigatórios no mesmo SHA.
- [ ] Adicionar `/checkpoint` em pt-BR.
- [ ] Atualizar `docs/as-built/` com IDs/names/volumes/imagens reais não sensíveis.
- [ ] Não fazer merge automático.

### Task 9 — Slice separada core-l2jtoren

**Deliverable:** backlog pronto, sem alterar o runner L2jToren nesta foundation.

- [ ] Registrar relação com PR #757 do L2jToren.
- [ ] Definir migração `core -> core-l2jtoren` como PR independente.
- [ ] Preservar x99 runner até certificação completa.
- [ ] Não reutilizar GREEN de SHA anterior.
