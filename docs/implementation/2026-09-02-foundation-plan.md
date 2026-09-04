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

### Task 2 — Backlog inicial e baseline observado

**Deliverable:** Issues iniciais criadas e estado atual dos nós reconstruído antes da simulação.

- [x] Criar Issues #1–#14 com dependências explícitas.
- [x] Ler x99 sem alteração: Windows/WSL2, Docker/Compose, Tailscale e storage.
- [x] Ler Core sem alteração: OS/kernel, CPU/RAM/storage, Docker/Compose, Tailscale, failed units e container de runner.
- [x] Ler Pentium sem alteração: OS/kernel, CPU/RAM/storage, Tailscale, failed units, agent/timers e toolchain administrativa.
- [x] Consultar GitHub Actions runners dos repositórios L2jToren e DevEx HomeLab.
- [x] Atualizar `docs/as-built/2026-09-02-baseline.md` separando observed state de desired state/drift.
- [x] Validar working copy limpa e `git diff --check` no HEAD da certificação.

### Task 3 — Ambiente de simulação na x99 / Issue #14

**Deliverable:** Compose de desenvolvimento que valida a topologia lógica sem depender dos hosts reais.

- [x] Criar branch `devex/issue-14-docker-simulation` a partir do baseline certificado.
- [x] Criar `dev/simulation/compose.yaml` com `sim-core` e `sim-pentium` mínimos.
- [x] Criar imagens base Ubuntu 26.04 para os dois papéis.
- [x] Montar o repositório read-only e volumes nomeados separados para estado de teste.
- [x] Adicionar health checks que validem role, workspace read-only e state writable.
- [x] Validar `docker compose config`.
- [x] Construir imagens e subir os dois containers.
- [x] Aguardar ambos ficarem healthy.
- [x] Validar comunicação lógica `sim-pentium -> sim-core` na rede interna da simulação.
- [x] Derrubar o ambiente com `down -v --remove-orphans` e provar ausência de containers/volumes órfãos.
- [x] Abrir PR Draft empilhada sobre `foundation/issue-1-devex-homelab` e registrar `/checkpoint`.

### Task 4 — Stack do runner core-devex-homelab / Issue #8

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

- [x] Criar `.github/workflows/foundation-ci.yml` bootstrap em `ubuntu-latest` (Issue #17).
- [ ] Migrar `foundation-ci.yml` para `core-devex-homelab` após certificação do runner.
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

- [x] Abrir Draft PR #15 vinculada à Issue #1.
- [ ] Confirmar HEAD exato e changed files após as slices da foundation.
- [ ] Aguardar/validar todos os checks obrigatórios no mesmo SHA quando a CI existir.
- [x] Registrar checkpoints intermediários em pt-BR.
- [ ] Atualizar `docs/as-built/` com IDs/names/volumes/imagens finais da foundation.
- [ ] Não fazer merge automático.

### Task 9 — Slice separada core-l2jtoren

**Deliverable:** backlog pronto, sem alterar o runner L2jToren nesta foundation.

- [x] Registrar Issue #9 relacionando a migração com PR #757 do L2jToren.
- [x] Definir migração `core -> core-l2jtoren` como slice independente.
- [ ] Preservar x99 runner até certificação completa.
- [ ] Não reutilizar GREEN de SHA anterior.
