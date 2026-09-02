# Implementation Design — x99 Docker Simulation

Issue: #14  
PRD: `docs/prd/PRD-0014-x99-docker-simulation.md`

## Decisão

A simulação usa Docker Compose com dois serviços persistentes apenas durante a verificação. Não há tentativa de emular hosts completos; validamos os contratos que serão reutilizados pelas stacks reais.

## Componentes

### sim-core

- base `ubuntu:26.04`;
- papel `homelab.compute`;
- listener TCP interno na porta 19090;
- `/workspace` read-only;
- `/state` em volume próprio;
- usuário `ubuntu` UID/GID 1000.

### sim-pentium

- base `ubuntu:26.04`;
- papel `homelab.control`;
- depende de `sim-core` healthy;
- `/workspace` read-only;
- `/state` em volume próprio;
- usuário `ubuntu` UID/GID 1000.
## Rede e estado

A rede `devex-homelab-sim-net` é exclusiva da stack. Os volumes `devex-homelab-sim-core-state` e `devex-homelab-sim-pentium-state` não são compartilhados.

O bind mount da raiz do repositório é read-only para impedir que a simulação altere a working copy.

## Health contract

Cada serviço só fica healthy quando:

- o arquivo de role existe e contém o papel esperado;
- `/state` é writable;
- `/workspace` está montado;
- no Core, o listener interno responde.

## Verificação

`dev/simulation/verify.sh` executa em sequência:

1. `docker compose config`;
2. build das imagens;
3. `up -d --wait`;
4. inspeção de UID, role e mount `RW=false`;
5. prova de escrita em `/state`;
6. probe Pentium → Core;
7. `down -v --remove-orphans`;
8. prova de cleanup completo.
## Compatibilidade x99

Git Bash/MSYS converte caminhos Unix antes de passá-los ao `docker.exe`. O verificador define `MSYS_NO_PATHCONV=1` para preservar argumentos como `/state/role` e `/workspace`.

A imagem Ubuntu 26.04 já contém `ubuntu:x:1000:1000`; por isso o design reutiliza esse usuário em vez de criar um segundo UID 1000.

## Falhas e cleanup

O script usa `trap` para executar cleanup mesmo quando uma etapa falha. Isso evita deixar containers, redes ou volumes de teste órfãos.

## Limites

A certificação desta slice não autoriza deploy físico. Core e Pentium continuam exigindo gates próprios no HEAD exato.