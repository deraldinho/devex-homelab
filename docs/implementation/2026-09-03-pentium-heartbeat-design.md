# Implementation Design — Pentium Heartbeat / Issue #4

## Base e dependência

- branch base: `net/issue-3-management-network`;
- PR ancestral: #18;
- SHA ancestral certificado antes da slice: `c4f2917736ef6d763bfd002305b5533f94bfb5f1`;
- deploy físico: fora da etapa de implementação/CI até existir acesso administrativo autenticado ao Pentium.

## Arquitetura

`heartbeat.py` é stdlib-only e executa checks locais fixos. Para reachability do Core, ele não duplica lógica de Tailscale: invoca a cópia implantada de `infrastructure/network/health.py` com `--target core --json`.

O instalador copia para `~/pentium-agent/health/`:

- `heartbeat.py`;
- `config.json`;
- `network_health.py`;
- `network_inventory.json`.

As units são instaladas em `~/.config/systemd/user/`.

## Check pipeline

1. validar Linux + hostname `pentium`;
2. consultar `tailscaled.service` no system manager;
3. consultar agent/sentinel/jobs no user manager;
4. abrir SQLite em modo read-only e executar `PRAGMA quick_check`;
5. observar `MemAvailable` em `/proc/meminfo` e disco livre;
6. chamar network health para `core`;
7. reduzir checks obrigatórios para `healthy/degraded`;
8. persistir `latest.json` por write + fsync + `os.replace`;
9. emitir linha ASCII para journal/terminal.

## Systemd

`pentium-heartbeat.service` é `Type=oneshot`.

- exit `0`: healthy;
- exit `1`: degraded e aceito por `SuccessExitStatus=1`;
- exit `2`: erro de execução e unit failure.

`pentium-heartbeat.timer` executa após 1 minuto do boot e novamente a cada 1 minuto, com `Persistent=true`.

## Segurança

O heartbeat não recebe comando arbitrário. Os únicos processos externos são construídos pelo código:

- `systemctl [--user] is-active <unit-fixa>`;
- Python executando `network_health.py` com target fixo `core`.

Não há restart, deploy, escrita em SQLite, alteração de ACL ou alteração de Tailscale.

## TDD observado

### RED

SHA `30fbb1fcd2a34765a01b90c646e5aa26dfedbe91`:

- network contract ancestral: GREEN;
- heartbeat: RED;
- causa: `ModuleNotFoundError: No module named 'heartbeat'`;
- run `33779391280`, job `100729038275`.

### GREEN inicial

SHA `ed0771ed1e37f019b82b5d14e0910edd61cf7f53`:

- implementação mínima adicionada;
- heartbeat step passou no run subsequente;
- o HEAD ainda não é o HEAD final da slice porque config/systemd/docs foram adicionados depois.

## Certificação final esperada

O HEAD final precisa repetir:

- `git diff --check`;
- secret/content scan;
- network contract tests;
- heartbeat `py_compile` + tests;
- JSON config validation;
- `bash -n` do instalador;
- `systemd-analyze verify` das units quando disponível;
- marcadores de network, heartbeat e foundation no mesmo SHA.
