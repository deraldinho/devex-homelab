# PRD-0003 — Management Network Tailscale-first

## Contexto

O DevEx HomeLab usa Tailscale como caminho administrativo entre `pentium`, `core` e `x99`. A Issue #3 formaliza essa malha antes da evolução do Pentium Agent da Issue #4.

## Objetivo

Versionar o inventário não secreto da rede de gerenciamento e fornecer uma verificação reproduzível de reachability capaz de distinguir:

- nó presente e online no tailnet;
- IP Tailscale observado igual ao inventário;
- endpoint SSH TCP/22 alcançável;
- degradação de nó obrigatório sem depender da x99 para operação permanente.

## Escopo

- `pentium` como `homelab.control`;
- `core` como `homelab.compute`;
- `x99` como workstation opcional;
- nomes e IPv4 Tailscale não secretos;
- health check em Python 3 sem dependências externas;
- saída humana ASCII e saída JSON;
- testes unitários do contrato;
- integração do teste ao CI da foundation.

## Fora de escopo

- alterar ACLs, chaves, autenticação SSH ou configuração do Tailscale;
- Wake-on-LAN;
- auto-remediação;
- armazenar tokens, private keys ou credenciais;
- provar autenticação SSH; esta slice prova reachability do endpoint TCP.

## Requisitos

1. `pentium` e `core` são nós obrigatórios para o estado global `healthy`.
2. `x99` é observável, mas sua falha não derruba o estado global.
3. O status Tailscale é lido de `tailscale status --json`.
4. O IP observado deve corresponder ao IPv4 versionado.
5. O endpoint SSH deve aceitar conexão TCP no endereço inventariado.
6. Falha em qualquer requisito de nó obrigatório resulta em `degraded` e exit code `1`.
7. Erro de contrato/execução resulta em exit code `2`.
8. Nenhuma operação corretiva é executada pelo health check.

## Critérios de aceitação

- testes cobrem self/peers do Tailscale, healthy, degraded, inventário inválido e saída ASCII;
- `git diff --check` passa;
- CI executa os testes no HEAD exato;
- execução em host com Tailscale pode emitir JSON utilizável pelo futuro Pentium heartbeat;
- nenhum secret é versionado.
