# As-Built — Core Compute Node

Data local: 2026-09-02
Issue: #5

## Observed state certificado

- hostname: `core`;
- papel: `homelab.compute`;
- Ubuntu 26.04.1 LTS, kernel 7.0.0-30;
- Docker Server 29.1.3;
- Docker Compose 2.40.3;
- Tailscale operacional;
- timezone `America/Sao_Paulo`;
- Docker `live-restore=true`, logs json-file 10m × 3;
- sleep/suspend/hibernate/hybrid-sleep mascarados;
- lid switch ignorado;
- SSH sem password/root login, pubkey habilitado;
- wait-online com `--any --timeout=30`;
- zero unidades systemd falhadas;
- `~/projects` ausente;
- `javac`, Ant, Node, npm e Codex ausentes do PATH do host.

## Estado de infraestrutura existente

`~/homelab` contém bootstrap/verificação, policy e stacks `smoke` + runner legado.

O runner atual `github-runner-core` / GitHub runner `core` é legado e não foi promovido a desired state nesta slice.

## Evidência

O verificador versionado foi executado no Core real via arquivo temporário em `/tmp` e removido após a execução.

Saída terminal relevante:

```text
docker=29.1.3
Docker Compose version 2.40.3+ds1-0ubuntu1
CORE_COMPUTE_CERTIFICATION_PASS
```

O teste de repositório na x99 retornou:

```text
CORE_REPO_POLICY_PASS
```

## Drift

Para o escopo de #5: **nenhum drift físico detectado**. Não houve reinstalação, alteração de SSH, Docker daemon, systemd, timezone, rede ou storage.

Dívidas fora do escopo permanecem em #7/#8/#9 para a plataforma de runners.
