# Core Runner Pool v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Materializar dois runners L2jToren e um runner DevEx HomeLab no Core, todos containerizados e registrados separadamente no GitHub.

**Architecture:** O Core hospeda três containers independentes com volumes persistentes separados e acesso controlado ao Docker socket. O L2jToren usa dois runners concorrentes; apenas `core-l2jtoren-01` recebe `l2jtoren-heavy`. O x99 deixa de ser dependência operacional somente após certificação GREEN.

**Tech Stack:** Docker Engine, Docker Compose, GitHub Actions Runner 2.337.0, Eclipse Temurin JDK 26, Bash, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-06-core-runner-pool-v2-design.md`

## Global Constraints

- Nunca versionar registration tokens.
- Cada runner tem nome, registro e volume `_work` próprios.
- Docker capability só existe quando `docker version`, `docker compose version` e container descartável passam.
- `core-l2jtoren-01` é o único runner com `l2jtoren-heavy` inicialmente.
- O runner legado x99 não é removido antes da certificação dos três novos runners.

---

### Task 1: Contrato e manifests
- [x] Criar teste de contrato antes dos manifests e confirmar RED.
- [x] Criar Dockerfile multi-target, entrypoint e compose com três serviços.
- [ ] Executar contrato e `docker compose config` até GREEN.

### Task 2: Publicação versionada
- [ ] Commitar manifests e plano na branch `infra/core-runner-pool-v2` do `devex-homelab`.
- [ ] Publicar branch sem segredos.
### Task 3: Bootstrap no Core
- [ ] Gerar tokens temporários de registro para L2jToren e DevEx HomeLab.
- [ ] Executar bootstrap no runner `core` existente.
- [ ] Buildar imagens e subir `core-l2jtoren-01`, `core-l2jtoren-02`, `core-homelab-01`.
- [ ] Recriar containers sem tokens após o registro persistir nos volumes.

### Task 4: Certificação
- [ ] Confirmar os três runners online no GitHub.
- [ ] Validar Java/Javac 26 e Ant nos dois runners L2jToren.
- [ ] Validar Python/Git/Docker/Compose nos três runners.
- [ ] Validar container descartável via Docker socket.
- [ ] Validar volumes independentes e ausência de tokens persistidos.

### Task 5: Migração segura
- [ ] Migrar selectors dos workflows L2jToren para `[self-hosted, core, l2jtoren, docker]` em PR de infraestrutura.
- [ ] Migrar workflows HomeLab para `[self-hosted, core, devex-homelab]`.
- [ ] Rerodar CI Runtime do HEAD autoritativo do L2jToren.
- [ ] Só retirar x99 da função obrigatória após evidência GREEN.
