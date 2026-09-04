# PRD-0005 — Core Compute Node

Issue: #5 — Compute: reconciliar Core como plataforma container-first

## Problema

O Core já executa parte da infraestrutura do HomeLab, mas o estado permanente do host precisa ser representado no Git como desired state verificável, sem transformar o host em workspace de desenvolvimento.

## Objetivo

Formalizar e certificar `core` como `homelab.compute`, mantendo o host mínimo e delegando toolchains/projetos a containers.

## Requisitos

- Ubuntu 26.04 como baseline de SO;
- administração via Tailscale/SSH;
- Docker e Compose operacionais;
- timezone `America/Sao_Paulo`;
- Docker `live-restore` e rotação de logs;
- targets de sleep/suspend/hibernate mascarados;
- lid switch ignorado;
- SSH somente por chave, sem root/password login;
- zero unidades systemd falhadas;
- nenhum JDK/Ant/Node/npm/Codex no host;
- nenhum `~/projects` no host;
- smoke Docker reproduzível.

## Fora de escopo

- registrar ou renomear runners GitHub;
- instalar toolchain de projeto no host;
- migrar o runner legado `core`;
- alterar Tailscale, storage ou rede sem drift comprovado.

## Critérios de aceite

1. contratos do Core versionados em `infrastructure/core/`;
2. `validate-repo.sh` passa em Docker local/CI;
3. `verify-core.sh` passa no Core real;
4. observed state e desired state não apresentam drift da slice #5;
5. runner legado é documentado como dívida das Issues #7/#8/#9;
6. CI GREEN no HEAD exato da PR;
7. checkpoint e as-built registrados.
