# PRD-0014 — Simulação Docker da Topologia DevEx HomeLab

Issue: #14  
Status: Implementado / aguardando revisão da PR

## Problema

Mudanças de infraestrutura destinadas a Core e Pentium não devem ser testadas primeiro nos hosts físicos. O projeto precisa de um ambiente local reproduzível na x99 que valide contratos lógicos antes da certificação real.

## Objetivo

Fornecer uma stack Docker mínima capaz de representar os papéis `homelab.compute` e `homelab.control`, validar comunicação entre eles, isolamento de estado, permissões e lifecycle completo.

## Usuário

Mantenedor do DevEx HomeLab desenvolvendo em `C:\Users\deral\DevEx-HomeLab`.

## Requisitos funcionais

- criar `sim-core` e `sim-pentium`;
- usar Ubuntu 26.04 como base lógica;
- expor roles canônicos por arquivo de estado;
- permitir `sim-pentium -> sim-core` na rede da simulação;
- validar saúde antes de aceitar o ambiente;
- remover containers, volumes e rede ao final da certificação.
## Requisitos não funcionais

- nenhuma credencial real na simulação;
- working copy montada read-only;
- estado de cada nó em volume separado;
- containers executados como UID/GID 1000;
- nenhuma dependência em Core ou Pentium reais para o teste local;
- resultado reproduzível via um único script de verificação.

## Critérios de aceite

1. `docker compose config` retorna sucesso.
2. As duas imagens constroem.
3. Ambos os serviços ficam `healthy`.
4. `/workspace` possui `RW=false`.
5. `/state` aceita escrita.
6. O Core simulado retorna `DEVEX_SIM_CORE_OK` ao Pentium simulado.
7. O teardown deixa zero containers, volumes e redes da stack.
8. A execução final emite `DEVEX_HOMELAB_SIMULATION_PASS`.

## Fora de escopo

Kernel real, systemd host, Tailscale real, WOL, BIOS, storage físico, bateria e qualquer deploy em Core/Pentium.