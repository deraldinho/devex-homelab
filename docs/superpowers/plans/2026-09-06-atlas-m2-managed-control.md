# Atlas M2 Managed CONTROL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar CONTROL administrativo tipado e auditavel para hosts MANAGED sem shell arbitrario.

**Architecture:** `PolicyCapabilities` continua como autoridade; M2 recebe somente decisoes autorizadas, valida host/op/alvo contra inventario e executa comandos fixos via `SshTransport`. Reboot permanece DESTRUCTIVE com confirmacao humana independente.

**Tech Stack:** Python stdlib, unittest, OpenSSH, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-06-atlas-m2-managed-control-design.md`

## Global Constraints
- Base: `bc94198c8b263f22ef04e57ae027edb4829cd987`.
- Nenhuma API publica aceita shell arbitrario.
- Default-deny antes do SSH.
- Autorizacao exata por host + operacao + alvo.
- Reboot exige confirmacao humana validada.
- Auditoria pre-execucao e pos-resultado.
- Sem retry autonomo de CONTROL.

---

### Task 1: Inventario CONTROL allowlisted
**Files:** `managed_inventory.py`, `test_managed_inventory.py`
**Produces:** `allowed_controls` e alvos de servico explicitamente cadastrados por host.

### Task 2: ManagedControlService default-deny
**Files:** create `managed_control.py`, test `test_managed_control.py`
**Produces:** operacoes tipadas START/STOP/RESTART_SERVICE e REBOOT_HOST; zero SSH em decisao/parametro/host/alvo invalido.

### Task 3: Auditoria fail-closed
**Files:** create `control_audit.py`, extend `managed_control.py`, tests correspondentes.
**Produces:** `ControlAuditRecord` e sink auditavel; falha de pre-audit bloqueia execucao.

### Task 4: Integracao policy/capabilities
**Files:** `capability_registry.py`/config ou factory existente, `policy_capabilities.py`, tests.
**Produces:** capabilities M2 coerentes com C4, reboot DESTRUCTIVE.

### Task 5: Packaging e certificacao
**Files:** installer, Foundation CI, architecture/PRD docs, packaging tests.
**Produces:** marker `DEVEX_HOMELAB_ATLAS_MANAGED_CONTROL_M2_PASS`, PR Draft, exact-head CI e checkpoint.
