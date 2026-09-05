# Implementation Design — Management Network / Issue #3

## Base

- base: `foundation/issue-1-devex-homelab`
- owner: DevEx HomeLab
- deployment: nenhum nesta slice; somente desired state e probes não destrutivos

## Componentes

### `infrastructure/network/inventory.json`

Inventário explícito e não secreto de nós. Cada entrada declara role, nome Tailscale, IPv4, porta SSH e se o nó participa do gate global.

### `infrastructure/network/health.py`

Probe Python 3 stdlib-only. O fluxo é:

1. validar schema do inventário;
2. executar `tailscale status --json`;
3. indexar `Self` e `Peer` por hostname;
4. comparar IPv4 observado com o desired state;
5. abrir conexão TCP na porta SSH;
6. classificar cada nó como `healthy` ou `degraded`;
7. reduzir somente nós `required=true` para o estado global;
8. emitir texto ASCII ou JSON e exit code estável.

## Semântica de estado

`healthy` exige simultaneamente:

- peer/self online segundo Tailscale;
- IPv4 sem drift;
- TCP/22 alcançável.

`degraded` não tenta corrigir rede, reiniciar serviços ou modificar ACL/SSH.

## Exit codes

- `0`: todos os nós obrigatórios healthy;
- `1`: pelo menos um nó obrigatório degraded;
- `2`: erro de configuração, Tailscale CLI, JSON ou execução.

## Segurança

O inventário não contém chaves nem tokens. A verificação TCP não autentica e não executa comandos remotos. Alterações em SSH/Tailscale continuam exigindo aprovação explícita e slice própria.

## TDD e validação

O teste inicial foi escrito antes do módulo e falhou por `ModuleNotFoundError`, estabelecendo o RED. Depois da implementação, cinco testes de domínio passaram. A primeira execução real no x99 revelou saída Unicode incompatível com `cp1252`; foi adicionada regressão específica e o formato foi alterado para ASCII (`ok`/`fail`).

## Relação com Issue #4

A Issue #4 deve consumir este contrato como camada de rede do heartbeat do Pentium. O heartbeat adicionará saúde local de OS, Tailscale daemon, `pentium-agent`, `pentium-sentinel.timer`, `pentium-jobs.timer` e SQLite sem duplicar a lógica de reachability.
