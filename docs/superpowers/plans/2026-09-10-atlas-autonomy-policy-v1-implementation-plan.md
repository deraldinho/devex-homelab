# Atlas Autonomy Policy v1 Implementation Plan

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar o Nível 2 de autonomia controlada da Atlas, permitindo autorização automática e execução segura de reinício de serviços locais (`atlas-observation.service`, `atlas-dashboard.service`) no Pentium, com quatro travas obrigatórias (allowlist, cooldown, budget e verificação closed-loop).

**Architecture:** `PolicyCapabilities` avalia intenções de controle determinando a classe (`AUTO`, `CONFIRM`, `DENY`). `ActionPolicy` propaga a decisão ao `PlanoAcaoAtlas`. `SafeLocalCapabilityExecutor` despacha comandos de usuário (`systemctl --user restart`) e valida a recuperação via sondagem de estado.

**Spec:** `docs/superpowers/specs/2026-09-10-atlas-autonomy-policy-v1-design.md`

---

### Task 1: Travas de Cooldown e Budget em `PolicyCapabilities`

**Files:**
- Modify: `infrastructure/pentium/atlas/policy_capabilities.py`
- Test: `infrastructure/pentium/atlas/tests/test_autonomy_policy.py`

**Interfaces:**
- `PolicyCapabilities(..., cooldown_s: float = 300.0, max_auto_per_window: int = 2, window_s: float = 3600.0, clock=...)`
- `DecisaoCapability.autonomia in {"AUTO", "CONFIRM", "DENY"}`
- `registrar_execucao(capability: str, parametros: dict[str, object], quando: float | None = None)`

- [ ] Escrever testes para cooldown e estouro de budget resultando em `CONFIRM`.
- [ ] Implementar rastreamento de execuções com janela deslizante e cooldown em `PolicyCapabilities`.
- [ ] Executar `pytest test_autonomy_policy.py` e validar GREEN.

---

### Task 2: Closed-Loop Verification no `SafeLocalCapabilityExecutor`

**Files:**
- Modify: `infrastructure/pentium/atlas/autonomy_executor.py`
- Test: `infrastructure/pentium/atlas/tests/test_autonomy_executor.py`

**Interfaces:**
- `SafeLocalCapabilityExecutor(..., verifier=..., verify_timeout_s: float = 15.0)`
- `VerificationFailedError(RuntimeError)`
- Após restart com sucesso, invocar verificação; se falhar, lançar `VerificationFailedError`.

- [ ] Escrever testes para verificação bem-sucedida e falha de verificação com timeout.
- [ ] Implementar verificação closed-loop padrão usando `systemctl --user is-active <service>`.
- [ ] Executar `pytest test_autonomy_executor.py` e validar GREEN.

---

### Task 3: Integração no `ActionPolicy` e `ActionExecutorRegistry`

**Files:**
- Modify: `infrastructure/pentium/atlas/action_policy.py`
- Test: `infrastructure/pentium/atlas/tests/test_cognitive_action_runtime.py`

- [ ] Garantir que `ActionPolicy` respeita `decision.autonomia == "AUTO"`, liberando execução imediata sem exigir confirmação humana.
- [ ] Registrar a execução no histórico da policy após sucesso do executor.
- [ ] Executar testes da suíte de ações e validar GREEN.

---

### Task 4: Wiring no `cognitive_daemon.py`

**Files:**
- Modify: `infrastructure/pentium/atlas/cognitive_daemon.py`
- Test: `infrastructure/pentium/atlas/tests/test_autonomy_wiring.py`

- [ ] Injetar `SafeLocalCapabilityExecutor` como `capability_sink` no `ActionExecutorRegistry`.
- [ ] Configurar allowlists de host `pentium` e serviços `atlas-observation.service` e `atlas-dashboard.service`.
- [ ] Executar `pytest test_autonomy_wiring.py` e validar GREEN.

---

### Task 5: Certificação da Suíte Completa

- [ ] Executar toda a suíte de testes do Atlas:
  `python -m pytest infrastructure/pentium/atlas/tests/`
- [ ] Verificar ausência de regressões em chat, SSE e observabilidade.
