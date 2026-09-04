# Implementation Design — Pentium Agent / x99.status

## Base

- iniciativa: Issue #4;
- PR autoritativa: #19;
- base da slice: HEAD certificado `03f8b80c7df254285b03dc67fe338bc2edbe1b68`;
- canal físico já validado manualmente: Pentium -> x99 via Tailscale + SSH por chave.

## Arquitetura

A slice introduz um Agent mínimo versionado com três responsabilidades separadas:

1. `registry.py`: resolve nomes de ação permitidos;
2. `ssh_transport.py`: executa somente argv SSH construído pelo código;
3. `x99_status.py`: define a coleta somente-leitura e normaliza o resultado.

`agent.py` apenas recebe o nome da ação, consulta o registry e serializa o resultado. Nenhum comando remoto vem do chamador.

## Fluxo

`agent.py x99.status` -> registry -> `x99_status.run()` -> SSH transport -> PowerShell fixo no x99 -> parser -> JSON/resumo ASCII.

A configuração versiona somente dados não secretos: host `100.101.23.111`, usuário `deral`, caminho esperado da chave `~/.ssh/id_ed25519_x99`, timeout e política de host key.

## Contrato remoto

O comando remoto é PowerShell somente-leitura e produz uma única linha JSON com chaves estáveis:

- `hostname`;
- `identity`;
- `last_boot_utc`;
- `uptime_seconds`.

O Agent valida hostname esperado `x99`. Ausência de resposta, timeout, exit code SSH não zero, JSON inválido ou hostname divergente tornam a ação `degraded`.

## Segurança

O transporte usa lista argv, sem `shell=True`. Flags mínimas:

- `BatchMode=yes`;
- `ConnectTimeout=<config>`;
- `IdentityFile=<config>`;
- política de host key explícita.

Não haverá fallback por senha. A chave privada permanece apenas no Pentium.

## Testes

Os testes unitários não abrem conexão real. Um runner injetável captura argv e simula stdout/stderr/exit code. Devem cobrir allowlist, rejeição de ação, construção do SSH, resposta saudável, timeout/falha SSH, JSON inválido e hostname inesperado.

A certificação física ocorre somente depois do CI GREEN do HEAD exato e após inspeção do Agent instalado no Pentium, para evitar sobrescrever implementação host-only não reconciliada.

## Não escopo

`x99.health`, runner status, wake, deploy e remediação automática ficam para slices posteriores da mesma Issue #4.
