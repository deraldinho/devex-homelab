# Atlas M2 Managed CONTROL — Design

## Decisao

A M2 adiciona execucao administrativa tipada para hosts `MANAGED`, reutilizando o inventario e o `SshTransport` endurecido pela M1. A camada de policy continua fora do transporte: `PolicyCapabilities` decide autoridade; M2 executa somente uma decisao ja autorizada.

Nao existe API publica de shell arbitrario. A LLM pode sugerir uma intent estruturada, mas nao cria comandos, nao altera allowlists, nao aceita host keys e nao amplia privilegios.

## Escopo

Operacoes iniciais:

- `START_SERVICE`
- `STOP_SERVICE`
- `RESTART_SERVICE`
- `REBOOT_HOST`

`START/STOP/RESTART_SERVICE` sao CONTROL. `REBOOT_HOST` permanece DESTRUCTIVE e exige confirmacao humana independente antes de chegar ao executor.

## Arquitetura

```text
Intent estruturada
  -> CapabilityRegistry
  -> PolicyCapabilities
  -> Decisao autorizada
  -> ManagedControlService
  -> ManagedInventory
  -> catalogo CONTROL fixo
  -> SshTransport
  -> host MANAGED
  -> AuditRecord
```

## Regras de autorizacao

A autorizacao efetiva de CONTROL e vinculada a combinacao exata de `host_id + operation + target`. Permissao para `restart_service` em um servico nao autoriza outro servico nem outro host.

Sem decisao autorizada, nenhuma chamada SSH ocorre. Parametros invalidos, host desconhecido, host nao MANAGED, operacao fora da allowlist ou alvo nao autorizado falham fechado antes do transporte.

`REBOOT_HOST` nunca e promovido a CONTROL. O executor exige evidencia explicita de confirmacao humana ja validada pela policy para qualquer reboot.

## Catalogo remoto

Os comandos sao fixos por plataforma. Linux usa `systemctl start|stop|restart <service>` e `systemctl reboot`; Windows usa PowerShell nao interativo com `Start-Service`, `Stop-Service`, `Restart-Service` e `Restart-Computer`.

Nomes de servico devem corresponder exatamente a alvos cadastrados no inventario. Nenhuma interpolacao livre, pipe, redirecionamento ou fragmento de shell vindo da LLM e aceito.

## Auditoria e bounds

Cada tentativa produz um `ControlAuditRecord` pequeno e deterministico com host, operacao, alvo, autorizacao, resultado, motivo e timestamp. Falha de auditoria antes da execucao bloqueia a operacao; falha de persistencia do resultado final nunca inventa sucesso.

Toda execucao herda host-key estrita, timeout e limite de output da M1. Nao ha retry autonomo de CONTROL nesta slice.

## Testes e DoD

Cenarios obrigatorios: default-deny; combinacao host/op/alvo exata; parametro invalido sem SSH; host nao MANAGED sem SSH; reboot sem confirmacao sem SSH; comando fixo Linux/Windows; falha SSH isolada; audit record em sucesso/falha; ausencia de API de shell arbitrario; installer/CI/docs; Foundation CI GREEN no HEAD exato e `/checkpoint` na PR Draft empilhada sobre M1.

M2 nao implementa auto-remediacao, escalacao de privilegio, alteracao de firewall/rede/Tailscale, distribuicao de chaves ou shell generico.