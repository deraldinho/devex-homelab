# PRD-0005 — Pentium Agent / x99.status

## Contexto

O `pentium` é o nó `homelab.control` e deve observar o `x99` sem depender de senha interativa nem de shell arbitrário. O canal físico `Pentium -> x99` via Tailscale + SSH por chave já foi validado manualmente.

A Issue #4 exige versionar e evoluir o Pentium Agent. Esta slice inaugura o contrato versionado de ações remotas com uma única ação: `x99.status`.

## Objetivo

Permitir que o Pentium Agent consulte o estado básico do x99 por uma ação nominal, fixa e auditável, usando a chave SSH já provisionada fora do Git.

## Escopo funcional

`x99.status` deve retornar:

- identidade do host remoto;
- identidade do usuário remoto;
- uptime/último boot disponível pelo Windows;
- disponibilidade do canal SSH;
- status global `healthy` ou `degraded`;
- saída estruturada JSON e resumo humano ASCII.

## Contrato de execução

A ação não recebe comando, script ou argumentos arbitrários do usuário. O Agent resolve `x99.status` para uma operação SSH fixa, com destino versionado e identidade SSH configurada externamente.

O comando remoto deve ser PowerShell somente-leitura e coletar campos conhecidos. O transporte deve impor timeout, BatchMode e host-key checking; nenhuma senha é armazenada.

## Segurança

- sem chave privada, senha ou token no repositório;
- sem `Invoke-Expression`, `cmd /c` arbitrário ou shell fornecido pelo chamador;
- sem restart, wake, shutdown, alteração de runner, firewall, SSH ou Tailscale;
- falha SSH produz estado `degraded`, não tentativa automática de correção;
- logs não devem imprimir material de chave.

## Definition of Done

- contrato e design versionados na mesma stack da PR #19;
- TDD RED antes da implementação;
- registry aceita `x99.status` e rejeita ações desconhecidas;
- transporte SSH constrói somente argv fixo e testável;
- parser normaliza resposta do Windows;
- CI do HEAD exato passa network + heartbeat + Pentium Agent;
- deploy físico preserva o Agent existente até reconciliação explícita;
- `x99.status` executa com sucesso a partir do Pentium real;
- checkpoint da PR registra SHA, CI e evidência física separadamente.
