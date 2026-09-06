# Atlas M1 Managed SSH READ Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generalizar o SSH existente do Pentium para observacao READ tipada, bounded e fail-closed de hosts explicitamente MANAGED.

**Architecture:** O `SshTransport` permanece como transporte baixo nivel e recebe endurecimento de host-key/known_hosts e bounds. Uma camada `managed_inventory` resolve hosts autorizados e uma camada `managed_read` converte operacoes tipadas em comandos fixos, normaliza resultados e impede shell arbitrario. O `x99_status` passa a reutilizar essa fundacao sem alterar a separacao de M2 CONTROL.

**Tech Stack:** Python 3 stdlib, `unittest`, OpenSSH client, JSON, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-06-atlas-m1-managed-ssh-read-design.md`

## Global Constraints

- Base obrigatoria: `7d147657ebb4ddf285b998c45ea5fdb831fad11c`.
- Nenhuma API publica aceita shell arbitrario.
- Host desconhecido ou nao MANAGED falha antes de invocar SSH.
- `StrictHostKeyChecking=yes`, `BatchMode=yes`, `IdentitiesOnly=yes` e `UserKnownHostsFile` explicito.
- Toda operacao READ usa comando fixo allowlisted, timeout e output bounded.
- M2 CONTROL permanece fora de escopo.
- `x99_status` deve continuar funcional sobre a nova fundacao.

---

### Task 1: Managed Inventory fail-closed

**Files:**
- Create: `infrastructure/pentium/agent/managed_inventory.py`
- Test: `infrastructure/pentium/agent/tests/test_managed_inventory.py`

**Interfaces:**
- Produces: `ManagedHost`, `ManagedInventory`, `UnknownManagedHostError`, `HostNotManagedError`.
- `ManagedInventory.require_managed(host_id: str) -> ManagedHost` rejeita qualquer host fora de `MANAGED` antes do transporte.
- [ ] **Step 1: Write the failing tests**

```python
host = ManagedHost(host_id="x99", enrollment="MANAGED", user="deral", host="192.168.88.20", identity_file=Path("key"), known_hosts_file=Path("known_hosts"), platform="windows", allowed_reads=frozenset({"uptime"}))
inv = ManagedInventory([host])
self.assertEqual(inv.require_managed("x99"), host)
with self.assertRaises(UnknownManagedHostError): inv.require_managed("ghost")
with self.assertRaises(HostNotManagedError): ManagedInventory([replace(host, enrollment="IDENTIFIED")]).require_managed("x99")
```

- [ ] **Step 2: Run RED**

Run from repository root:
`python -m unittest infrastructure.pentium.agent.tests.test_managed_inventory -v`
Expected: FAIL because `managed_inventory` does not exist.

- [ ] **Step 3: Implement minimal inventory**

Use frozen dataclass validation: non-empty IDs/user/host/platform, positive timeout, explicit identity/known-hosts paths, immutable allowlist, duplicate host IDs rejected.

- [ ] **Step 4: Run GREEN and agent regression**

`python -m unittest infrastructure.pentium.agent.tests.test_managed_inventory infrastructure.pentium.agent.tests.test_ssh_transport infrastructure.pentium.agent.tests.test_x99_status -v`

- [ ] **Step 5: Commit**

`git commit -m "feat(atlas): adicionar inventario managed fail closed M1"`

### Task 2: Strict SSH target and bounded output

**Files:**
- Modify: `infrastructure/pentium/agent/ssh_transport.py`
- Modify: `infrastructure/pentium/agent/tests/test_ssh_transport.py`

**Interfaces:**
- `SshTarget` gains `known_hosts_file: Path` and `max_output_bytes: int`.
- `SshTransport.run()` always supplies `UserKnownHostsFile=<path>` and truncates/rejects output deterministically at the configured bound.
- [ ] **Step 1: Write RED tests**

Assert argv contains `StrictHostKeyChecking=yes`, `UserKnownHostsFile=<explicit>`, timeout remains bounded, and output above `max_output_bytes` returns a deterministic bounded error without propagating the oversized payload.

- [ ] **Step 2: Run RED**

`python -m unittest infrastructure.pentium.agent.tests.test_ssh_transport -v`

- [ ] **Step 3: Minimal transport hardening**

Validate positive `connect_timeout_seconds` and `max_output_bytes`; add explicit known-hosts option; bound stdout/stderr before constructing `SshResult`.

- [ ] **Step 4: Run GREEN**

`python -m unittest infrastructure.pentium.agent.tests.test_ssh_transport -v`

- [ ] **Step 5: Commit**

`git commit -m "feat(atlas): endurecer transporte ssh managed M1"`

### Task 3: Typed READ catalog

**Files:**
- Create: `infrastructure/pentium/agent/managed_read.py`
- Test: `infrastructure/pentium/agent/tests/test_managed_read.py`

**Interfaces:**
- Produces enum `ManagedReadOperation` for `CPU`, `MEMORY`, `DISK`, `UPTIME`, `TEMPERATURE`, `SERVICES`, `PROCESSES`, `NETWORK`, `CONTAINERS`, `LOGS`.
- Produces `ManagedReadService.read(host_id: str, operation: ManagedReadOperation) -> dict`.
- Uses only fixed commands selected by platform/operation; no caller-provided command string.

- [ ] **Step 1: Write RED tests**

Cover unknown host, operation not allowlisted, fixed-command dispatch, lane-independent SSH failure result, JSON/typed normalization for at least uptime and memory, and absence of a public arbitrary-shell method.

- [ ] **Step 2: Run RED**

`python -m unittest infrastructure.pentium.agent.tests.test_managed_read -v`

- [ ] **Step 3: Implement minimal typed catalog**

Create fixed Linux/Windows command maps. Parse only bounded outputs into small dictionaries and return `status=degraded` for transport/parser failure rather than inventing host health.

- [ ] **Step 4: Run GREEN**

`python -m unittest infrastructure.pentium.agent.tests.test_managed_read -v`

- [ ] **Step 5: Commit**

`git commit -m "feat(atlas): implementar catalogo read tipado M1"`
### Task 4: Migrate x99_status onto M1

**Files:**
- Modify: `infrastructure/pentium/agent/actions/x99_status.py`
- Modify: `infrastructure/pentium/agent/cli.py`
- Modify: `infrastructure/pentium/agent/config.json`
- Modify: `infrastructure/pentium/agent/tests/test_x99_status.py`
- Modify: `infrastructure/pentium/agent/tests/test_cli.py`

**Interfaces:**
- `build_agent()` constructs `ManagedInventory` + `ManagedReadService` from config.
- `collect_x99_status()` consumes typed `UPTIME`/host identity data instead of owning SSH command construction.

- [ ] **Step 1: Write RED tests** for schema v2 managed hosts, explicit `known_hosts_file`, and x99 status through the typed service.
- [ ] **Step 2: Run RED** with `python -m unittest infrastructure.pentium.agent.tests.test_cli infrastructure.pentium.agent.tests.test_x99_status -v`.
- [ ] **Step 3: Implement migration** preserving the existing public `x99.status` action and output contract.
- [ ] **Step 4: Run GREEN** for the full Pentium Agent suite.
- [ ] **Step 5: Commit** as `feat(atlas): migrar x99 status para managed read M1`.

### Task 5: Packaging, docs and exact-head certification

**Files:**
- Modify: `infrastructure/pentium/agent/install-user.sh`
- Modify: `.github/workflows/foundation-ci.yml`
- Modify: `docs/architecture/atlas-local-intelligence-design.md`
- Modify: `docs/prd/PRD-0006-atlas-local-intelligence.md`
- Test: add packaging assertions under `infrastructure/pentium/agent/tests/`.

- [ ] **Step 1: Write RED packaging tests** requiring M1 modules in installer/CI and marker `DEVEX_HOMELAB_ATLAS_MANAGED_SSH_READ_M1_PASS`.
- [ ] **Step 2: Run RED** for packaging tests.
- [ ] **Step 3: Update installer, CI and docs** without adding deploy or M2 CONTROL behavior.
- [ ] **Step 4: Run GREEN**: Pentium Agent suite, Atlas 335+ suite, `bash -n`, `git diff --check`.
- [ ] **Step 5: Commit** as `docs(atlas): oficializar managed ssh read M1`.
- [ ] **Step 6: Push Draft PR** stacked on `atlas/issue-20-s3-fast-dispatch`, then certify Foundation CI on the exact HEAD.
- [ ] **Step 7: Post `/checkpoint` only after exact-head CI GREEN**, including SHA, run ID, markers, gates and next safe step M2.
