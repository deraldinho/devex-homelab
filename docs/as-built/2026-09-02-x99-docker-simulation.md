# As-Built — Simulação Docker na x99

Data: 2026-09-02
Issue: #14 — DevEx: simular topologia lógica na x99 com Docker

## Objetivo certificado

Validar na x99 a topologia lógica mínima do DevEx HomeLab antes de implantar novos componentes em Core ou Pentium reais.

A simulação implementa:

- `sim-core` como `homelab.compute`;
- `sim-pentium` como `homelab.control`;
- imagens base `ubuntu:26.04`;
- rede Docker dedicada `devex-homelab-sim-net`;
- volumes independentes `devex-homelab-sim-core-state` e `devex-homelab-sim-pentium-state`;
- working copy montada em `/workspace` como read-only;
- estado de runtime em `/state` como writable;
- probe lógico do control plane para compute.

## Ambiente de certificação

- host: `x99`;
- Docker Engine: `29.7.2`;
- Docker Compose: `v5.5.0`;
- WSL2/Docker Desktop ativos;
- base Ubuntu usada no build: `ubuntu:26.04`;
- digest observado da base: `sha256:2260313b31c8c011cd2eebe728008efac1b3982be73eb71348ea2648d2c0e09b`.

## Implementação versionada

- `dev/simulation/compose.yaml`;
- `dev/simulation/core/Dockerfile`;
- `dev/simulation/core/entrypoint.sh`;
- `dev/simulation/pentium/Dockerfile`;
- `dev/simulation/pentium/entrypoint.sh`;
- `dev/simulation/verify.sh`;
- `dev/simulation/README.md`.

## Contratos observados

- `sim-core`: role `homelab.compute`;
- `sim-pentium`: role `homelab.control`;
- ambos executam como `ubuntu` UID/GID 1000;
- `/workspace`: mount read-only;
- `/state`: writable e isolado por nó;
- comunicação Pentium → Core retorna `DEVEX_SIM_CORE_OK`;
- ambos atingem estado `healthy` antes da certificação.

## Evidência automatizada

Comando canônico na x99:

```bash
bash dev/simulation/verify.sh
```
A execução completa deve terminar com:

```text
DEVEX_SIMULATION_RUNTIME_PASS
DEVEX_SIMULATION_CLEANUP_PASS
DEVEX_HOMELAB_SIMULATION_PASS
```

O cleanup foi validado com zero containers, zero volumes e zero redes da stack após `down -v --remove-orphans`.

## Incidentes encontrados durante implementação

1. `ubuntu:26.04` já possui UID/GID 1000 no usuário `ubuntu`; a tentativa inicial de `useradd --uid 1000` falhou corretamente. A implementação reutiliza o usuário existente.
2. Git Bash/MSYS converte caminhos `/...` ao chamar executáveis Windows. `verify.sh` define `MSYS_NO_PATHCONV=1` para preservar paths internos de containers.
3. A validação negativa por `touch` em mount read-only gerou stderr esperado que PowerShell tratou como exceção. O contrato passou a ser validado pelo metadata `RW=false` do mount, sem depender de erro proposital.

## Estado pós-certificação

Nenhum container, volume ou rede da simulação deve permanecer ativo. As imagens locais podem permanecer em cache para acelerar execuções futuras.

Nenhuma alteração operacional foi aplicada em Core ou Pentium nesta slice.
