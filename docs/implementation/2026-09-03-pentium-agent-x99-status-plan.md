# Pentium Agent x99.status — Implementation Plan

> **Para execução agentic:** implementar tarefa por tarefa com TDD, revisão entre tarefas e commits pequenos. Não avançar para deploy físico sem CI GREEN no HEAD exato.

**Goal:** Versionar a primeira ação real do Pentium Agent, `x99.status`, com registry nominal e transporte SSH fixo para o x99.

**Architecture:** O Agent resolve somente nomes de ações allowlisted. `x99.status` usa um transporte SSH dedicado, com identidade/configuração lida de arquivo e payload PowerShell fixo; o resultado remoto é JSON, reduzido localmente para `healthy/degraded` e resumo ASCII. Nenhuma chave privada, senha ou comando livre entra no repositório.

**Tech Stack:** Python 3 stdlib, OpenSSH client, PowerShell remoto no Windows x99, JSON, unittest, GitHub Actions.

**Spec:** `docs/implementation/2026-09-03-pentium-agent-x99-status-design.md`

## Global Constraints

- PR #19 permanece Draft e sem merge automático.
- Base lógica: HEAD documental `9794021c358ad5aafa0dd67da74b57c6bb0dc149` ou descendente GREEN.
- Apenas `x99.status` entra nesta slice.
- Sem shell arbitrário e sem argumentos de comando fornecidos pelo caller.
- Chave privada fica apenas no Pentium em `~/.ssh/id_ed25519_x99`.
- Destino administrativo padrão: `deral@100.101.23.111` via Tailscale.
- SSH deve ser não interativo, com timeout limitado e host-key checking habilitado.
- Falhas de rede/auth/parse retornam `degraded`; erro de configuração local inválida retorna exit `2`.
- Deploy físico exige reconciliação prévia com o Agent já instalado no Pentium.

---
### Task 1: Congelar contrato RED do Agent

**Files:**
- Create: `infrastructure/pentium/agent/tests/test_agent.py`
- Modify: `.github/workflows/foundation-ci.yml`

**Interfaces:**
- Consumes: contrato `x99.status` do PRD-0005.
- Produces: testes que exigem `Agent`, registry allowlisted e rejeição de ação desconhecida.

- [ ] Criar testes importando `Agent` de `agent.py` e verificando `available_actions() == ("x99.status",)`.
- [ ] Testar `execute("unknown")` como erro de contrato sem subprocesso.
- [ ] Adicionar gate condicional `Pentium Agent` ao Foundation CI.
- [ ] Executar `python3 -m unittest discover -s infrastructure/pentium/agent/tests -p 'test_*.py' -v` e comprovar RED por ausência de `agent.py`.
- [ ] Commit: `test(pentium): define x99.status agent contract`.

### Task 2: Implementar registry nominal mínimo

**Files:**
- Create: `infrastructure/pentium/agent/agent.py`
- Test: `infrastructure/pentium/agent/tests/test_agent.py`

**Interfaces:**
- Produces: `Agent.available_actions() -> tuple[str, ...]`; `Agent.execute(action: str) -> dict`.
- `Agent.execute` aceita exclusivamente nomes presentes no registry interno.

- [ ] Implementar registry imutável contendo somente `x99.status`.
- [ ] Rejeitar qualquer outro nome antes de tocar o transporte.
- [ ] Injetar handler de `x99.status` no construtor para teste isolado.
- [ ] Rodar testes do Agent e comprovar GREEN do registry.
- [ ] Commit: `feat(pentium): add allowlisted agent registry`.
### Task 3: Implementar transporte SSH fixo

**Files:**
- Create: `infrastructure/pentium/agent/ssh_transport.py`
- Create: `infrastructure/pentium/agent/tests/test_ssh_transport.py`
- Create: `infrastructure/pentium/agent/config.json`

**Interfaces:**
- Produces: `SshTarget`; `SshResult`; `SshTransport.run(target, remote_command) -> SshResult`.
- O transporte recebe comando apenas de código confiável do Agent; nunca de entrada externa.

- [ ] Testar construção exata de argv com `BatchMode=yes`, `ConnectTimeout`, `IdentitiesOnly=yes`, `StrictHostKeyChecking=yes` e identity file configurado.
- [ ] Testar timeout, exit não-zero e captura de stdout/stderr sem exceção não tratada.
- [ ] Implementar execução via `subprocess.run(..., shell=False)` com argv em lista.
- [ ] Validar `config.json` sem secrets e com destino `deral@100.101.23.111`.
- [ ] Rodar testes e `python3 -m json.tool infrastructure/pentium/agent/config.json`.
- [ ] Commit: `feat(pentium): add bounded ssh transport for x99`.

### Task 4: Implementar `x99.status`

**Files:**
- Create: `infrastructure/pentium/agent/actions/x99_status.py`
- Create: `infrastructure/pentium/agent/tests/test_x99_status.py`
- Modify: `infrastructure/pentium/agent/agent.py`

**Interfaces:**
- Produces: `collect_x99_status(transport, target) -> dict`.
- Remote payload é uma string PowerShell constante definida no módulo.

- [ ] Testar parse de resposta JSON válida com `hostname`, `user`, `last_boot` e `uptime_seconds`.
- [ ] Testar SSH indisponível, autenticação recusada, JSON inválido e hostname diferente de `x99` como `degraded`.
- [ ] Implementar payload PowerShell fixo que usa `Get-CimInstance Win32_OperatingSystem` e `[Environment]::MachineName`.
- [ ] Reduzir o resultado para JSON local estável e resumo ASCII.
- [ ] Ligar o handler ao registry `x99.status` sem adicionar ações extras.
- [ ] Rodar toda a suíte do Agent.
- [ ] Commit: `feat(pentium): implement x99 status action`.
### Task 5: Empacotar, validar CI e preparar deploy

**Files:**
- Create: `infrastructure/pentium/agent/install-user.sh`
- Modify: `.github/workflows/foundation-ci.yml`
- Modify: `docs/implementation/2026-09-03-pentium-agent-x99-status-design.md` somente para evidência as-built confirmada.

**Interfaces:**
- Installer copia código/config para `~/pentium-agent/agent/` sem copiar chave privada.
- CI produz marcador `DEVEX_HOMELAB_PENTIUM_AGENT_PASS` no mesmo SHA dos gates ancestrais.

- [ ] Escrever instalador idempotente que preserve `~/.ssh/id_ed25519_x99` e não altere `authorized_keys`, sshd ou Tailscale.
- [ ] Adicionar `py_compile`, JSON validation, unittest discovery e `bash -n` ao CI.
- [ ] Rodar localmente `git diff --check`, testes network, heartbeat e Agent.
- [ ] Push e aguardar Foundation CI do HEAD exato; não reutilizar GREEN anterior.
- [ ] Inspecionar logs do job e registrar marcadores/HEAD exatos.
- [ ] Antes do deploy, inventariar no Pentium o Agent existente, units e árvore `~/pentium-agent`.
- [ ] Reconciliar diferenças; se houver conflito arquitetural, parar sem sobrescrever.
- [ ] Instalar somente o HEAD certificado e executar `x99.status` fisicamente.
- [ ] Registrar `/checkpoint` na PR #19 com CI + evidência do host real.

## Critérios finais da slice

- ação desconhecida nunca alcança subprocesso;
- nenhum caller controla argv ou payload PowerShell;
- nenhum secret/chave privada é versionado;
- `x99.status` retorna `healthy` no canal físico validado ou `degraded` com erro estruturado;
- network + heartbeat + Agent ficam GREEN no mesmo HEAD;
- PR #19 continua Draft até certificação física satisfatória;
- nenhuma alteração em SSH/Tailscale do x99 ou Pentium é feita pelo instalador.
