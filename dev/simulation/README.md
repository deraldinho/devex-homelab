# Simulação Docker do DevEx HomeLab

Esta stack reproduz a **topologia lógica mínima** de Core e Pentium na x99 antes de qualquer mudança nos hosts reais.

## Componentes

- `sim-core`: representa `homelab.compute`;
- `sim-pentium`: representa `homelab.control`;
- `devex-homelab-sim-net`: rede Docker dedicada;
- `devex-homelab-sim-core-state`: estado isolado do Core simulado;
- `devex-homelab-sim-pentium-state`: estado isolado do Pentium simulado.

As duas imagens usam `ubuntu:26.04` e o usuário já existente `ubuntu` (UID/GID 1000).

## Contratos validados

- `docker compose config` válido;
- imagens constroem sobre Ubuntu 26.04;
- ambos os containers atingem `healthy`;
- `/workspace` monta a working copy do projeto como read-only;
- `/state` é writable e isolado por nó;
- roles são `homelab.compute` e `homelab.control`;
- `sim-pentium` alcança `sim-core` pela rede interna e recebe `DEVEX_SIM_CORE_OK`;
- teardown remove containers, volumes e rede da simulação.

## Execução na x99

A partir da raiz do projeto, usando Git Bash:

```bash
bash dev/simulation/verify.sh
```

O sucesso completo termina com:

```text
DEVEX_SIMULATION_RUNTIME_PASS
DEVEX_SIMULATION_CLEANUP_PASS
DEVEX_HOMELAB_SIMULATION_PASS
```

`verify.sh` define `MSYS_NO_PATHCONV=1` porque Git Bash/MSYS converteria caminhos Linux como `/state/role` antes de entregá-los ao `docker.exe`.

## Limites da simulação

Esta stack não tenta emular kernel, systemd, BIOS, Wi-Fi, Tailscale real, NVMe físico, bateria, Wake-on-LAN ou Docker daemon dos hosts. Esses elementos continuam exigindo certificação física em Core/Pentium.

A simulação valida contratos de container, volumes, permissões, roles, rede lógica e lifecycle. Ela não substitui a certificação real antes de deploy.
