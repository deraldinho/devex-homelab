# Atlas M1 — Managed SSH READ

## Decisão

M1 transforma o transporte SSH já existente no Pentium em uma fronteira genérica e segura de observação READ para hosts `MANAGED`.

A implementação reutiliza `infrastructure/pentium/agent/ssh_transport.py` como camada de transporte de baixo nível. O domínio M1 adiciona inventário explícito, catálogo READ tipado, normalização e bounds. Nenhuma API pública aceita comando shell arbitrário.

M1 não implementa CONTROL. Ações administrativas permanecem reservadas à M2.

## Base e dependências

Base certificada: `7d147657ebb4ddf285b998c45ea5fdb831fad11c`.

M1 assume D1/D2 disponíveis para descoberta e identidade, mas não promove automaticamente dispositivos observados a `MANAGED`. Apenas hosts presentes no inventário gerenciado podem ser consultados.

O fluxo alvo é:

```text
Managed Inventory -> Managed SSH READ -> SshTransport -> SSH
                               |
                               v
                      Structured READ result
                               |
                               v
                     ObservationRuntime / Atlas
```
## Managed Inventory

Cada host gerenciado possui identidade lógica explícita e configuração bounded. O contrato mínimo contém:

- `host_id` lógico estável;
- endereço autorizado;
- usuário remoto;
- plataforma suportada;
- caminho para identidade SSH local;
- `known_hosts` explícito;
- timeout de conexão;
- catálogo READ permitido.

Credenciais, chaves privadas e conteúdo de `known_hosts` não são versionados como segredo no repositório.

Host ausente do inventário falha fechado. Descoberta D1/D2 nunca concede acesso administrativo automaticamente.

## Transporte SSH

`SshTransport` continua sendo a única camada que monta e executa `ssh`.

O argv deve manter:

- `BatchMode=yes`;
- `IdentitiesOnly=yes`;
- `StrictHostKeyChecking=yes`;
- `UserKnownHostsFile=<arquivo explícito>`;
- `ConnectTimeout=<bound>`;
- `shell=False`;
- timeout total do processo.
## Catálogo READ tipado

M1 expõe capacidades, não comandos livres. O catálogo inicial cobre:

- CPU;
- memória;
- disco;
- uptime;
- temperatura quando suportada;
- serviços explicitamente cadastrados;
- processos resumidos;
- rede resumida;
- containers;
- logs somente quando explicitamente cadastrados.

Cada operação define comando fixo, parser, limite de saída e schema de resultado. Parâmetro desconhecido ou não allowlisted é rejeitado antes do transporte.

O catálogo não possui `run_shell(command)`, `exec(command)` ou equivalente público.

## Normalização e bounds

A saída SSH bruta nunca é propagada diretamente ao motor afetivo, contexto cognitivo ou LLM.

Cada operação possui limite explícito de bytes/linhas e retorna estrutura reduzida e determinística. Saída acima do limite falha fechado ou é truncada apenas quando a operação declarar truncamento seguro e observável.

Timeout, retorno SSH não zero, host-key divergente e erro de parsing produzem falha estruturada sem bloquear outros hosts.
## Compatibilidade e migração

`x99_status` deve continuar funcional. A slice migra o caso específico para consumir a nova fronteira M1, evitando dois stacks SSH concorrentes.

A compatibilidade é comportamental: callers existentes mantêm resultado equivalente enquanto transporte, inventário e catálogo passam a ter ownership explícito.

## Segurança

- nenhuma promoção automática de `DISCOVERED`/`IDENTIFIED` para `MANAGED`;
- host-key checking nunca é desabilitado;
- nenhuma aceitação automática de host key nova;
- nenhuma chave privada no Git;
- nenhuma operação CONTROL nesta slice;
- nenhuma autoridade concedida à LLM para escolher shell, credencial ou host key;
- falha de SSH representa falha do canal administrativo, não prova isolada de falha física do host.

## Integração com ObservationRuntime

M1 fornece uma fonte/adaptador que reduz resultados READ para `SourceSnapshot`. O `ObservationRuntime` permanece owner de polling, timeout de fonte, backoff, jitter, deduplicação e journal.

M1 não cria scheduler paralelo nem loop infinito próprio.

A falha da zona `MANAGED` não deve bloquear `WIFI_OBSERVED`.
## Testes obrigatórios

- host desconhecido é rejeitado antes do SSH;
- host-key estrita e `known_hosts` explícito constam no argv;
- operação fora do catálogo é rejeitada;
- parâmetro inválido não alcança o transporte;
- READ retorna estrutura bounded;
- output acima do bound é tratado deterministicamente;
- timeout e retorno SSH não zero viram falha estruturada;
- falha de um host não bloqueia outro;
- `x99_status` preserva compatibilidade;
- nenhuma API pública aceita shell arbitrário;
- installer e Foundation CI empacotam e validam M1.

## Definition of Done

M1 fecha quando:

1. inventário gerenciado e catálogo READ estão implementados por TDD;
2. `SshTransport` aplica contrato estrito de host key e bounds;
3. `x99_status` usa a nova fronteira sem regressão;
4. integração mínima com `ObservationRuntime` está testada;
5. documentação, installer e Foundation CI possuem marker M1;
6. suíte local está GREEN;
7. Foundation CI está GREEN no HEAD exato;
8. checkpoint `/checkpoint` registra SHA e evidências.

M2 CONTROL e I1 Certification ficam fora desta slice.
