# PRD-0004 — Pentium Control-Plane Heartbeat

## Contexto

O `pentium` é o nó `homelab.control` do DevEx HomeLab. O baseline registra `pentium-agent`, `pentium-sentinel.timer` e `pentium-jobs.timer` ativos, porém o estado operacional ainda não possui um heartbeat versionado e persistente.

A Issue #4 depende da malha administrativa da Issue #3. Esta slice implementa somente a camada de heartbeat; a evolução posterior de comandos por projeto permanece na mesma iniciativa.

## Objetivo

Produzir, a cada minuto, um observed state local e legível por máquina que responda se o cérebro operacional está funcional, e não apenas ligado na rede.

## Checks obrigatórios

- hostname esperado `pentium` em Linux;
- `tailscaled.service` ativo;
- `pentium-agent.service` ativo no user manager;
- `pentium-sentinel.timer` ativo no user manager;
- `pentium-jobs.timer` ativo no user manager;
- `PRAGMA quick_check` em `~/pentium-agent/data/control.db`;
- mínimo de 10% de disco livre;
- mínimo de 256 MiB de memória disponível;
- `core` healthy segundo o contrato Tailscale/SSH da Issue #3.

## Saídas

### Humana

`PENTIUM: HEALTHY | OS=ok | TAILSCALE=ok | AGENT=ok | SENTINEL=ok | JOBS=ok | DB=ok | RESOURCES=ok | CORE=ok`

A saída é exclusivamente ASCII para funcionar em journal, CI e terminais Windows/Linux.

### Máquina

Snapshot JSON atômico em:

`~/pentium-agent/data/health/latest.json`

O snapshot contém timestamp UTC, status global, checks individuais e métricas de memória/disco.

## Semântica

- `healthy`: todos os checks obrigatórios passam;
- `degraded`: um ou mais checks operacionais falham;
- erro: configuração/execução não permite produzir observed state confiável.

Exit codes:

- `0`: healthy;
- `1`: degraded;
- `2`: erro de execução/contrato.

O serviço systemd aceita `0` e `1` como execução válida; somente erro `2` deve marcar a execução como falha.

## Segurança

- sem shell arbitrário;
- somente comandos fixos `systemctl is-active` e o health contract versionado da rede;
- SQLite aberto read-only para `quick_check`;
- nenhuma credencial ou chave é versionada;
- nenhuma auto-remediação nesta slice.

## Definition of Done

- TDD RED e GREEN comprovados em SHAs distintos;
- heartbeat e network contract passam no CI do mesmo HEAD final;
- units e instalador passam validação sintática;
- PR permanece Draft até deploy físico/certificação no Pentium;
- deploy só ocorre por versão aprovada e acesso autenticado;
- checkpoint registra o que está validado em CI e o que ainda exige host real.
