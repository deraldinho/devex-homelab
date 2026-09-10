# Atlas Autonomy Policy v1 Design

## Contexto e Objetivo

A Atlas opera hoje com separação clara de responsabilidades:
`observação → inferência cognitiva (Hermes) → plano de ação → política (ActionPolicy) → executores`

O modelo de linguagem Hermes propõe intenções estruturadas (`intencao`, `parametros_intencao`), mas **não possui autoridade direta de execução**, acesso a shell, credenciais ou filesystem do host.

O objetivo da **Autonomy Policy v1** é permitir que a política de ações autorize classes específicas de intervenção segura e reversível de forma **automática** (`AUTO`), sem intervenção humana a cada ciclo, mantendo controle rígido através de travas determinísticas (*defense-in-depth*).

## Taxonomia de Níveis de Autonomia

| Nível | Nome | Descrição | Comportamento da Policy |
| :--- | :--- | :--- | :--- |
| **0** | **Observador** | Leitura de estado, geração de diagnóstico e resposta textual/chat. | Sempre autorizado (`AUTO`). |
| **1** | **Autonomia Segura** | Ações visuais (avatar, expressão, postura), registro de contexto e memória, atualização de cache. | Ações reversíveis e locais (`AUTO`). |
| **2** | **Operacional Controlado** | Restart de serviços de usuário da própria Atlas no Pentium em degradação, limpeza de temporários e recarga de estado. | **Foco desta slice (v1)**. Autorizado dentro de limites estritos (`AUTO` com travas). |
| **3** | **Infraestrutura Limitada** | Ações em hosts remotos ou containers (`core`, `x99`), como reinício de runner ou container específico. | Requer confirmação por padrão (`CONFIRM`), permitindo `AUTO` apenas com profiles explícitos futuros. |
| **4** | **Ação Crítica** | Firewall, SSH, credenciais, Git, deploy, update de SO ou exclusão de arquivos. | **Sempre exige confirmação humana** (`CONFIRM`), nunca automático. |

## As Quatro Travas Obrigatórias (Nível 2 — v1)

Para que uma ação de controle seja classificada como `AUTO`, todas as quatro condições devem ser satisfeitas:

1. **Allowlist Estrita de Host e Serviços**:
   - `host == "pentium"` (rejeita qualquer host remoto).
   - `service in {"atlas-observation.service", "atlas-dashboard.service"}`.
   - Capability permitida: `"restart_service"`.
2. **Cooldown Temporal**:
   - Intervalo mínimo de 300 segundos (5 minutos) entre tentativas no mesmo serviço.
   - Se uma nova tentativa ocorrer antes do cooldown, o circuit breaker desarma e a ação é escalada para `CONFIRM`.
3. **Orçamento de Intervenções (Action Budget)**:
   - Máximo de 2 execuções autônomas por serviço em uma janela deslizante de 3600 segundos (1 hora).
   - Se o orçamento for excedido, a ação é classificada como `CONFIRM`, exigindo aprovação manual para evitar loops contínuos de reinicialização.
4. **Verificação Fechada (Closed-Loop Verification)**:
   - O executor não conclui com o mero disparo de `systemctl --user restart <service>`.
   - Realiza sondagem (`systemctl --user is-active <service>`) com timeout bounded (ex: 15s).
   - Se o serviço não atingir `active`, levanta `VerificationFailedError` e transiciona o status da ação para `FAILED`, gerando evento de auditoria.

## Máquina de Decisão (`AUTO`, `CONFIRM`, `DENY`)

```text
Entrada: capability, parametros, historico_execucoes

1. Capability desconhecida ou parametros invalidos?
   -> DENY (rejeição determinística)

2. Nivel da capability == "READ"?
   -> READ na allowlist?
      SIM -> AUTO
      NAO -> DENY

3. Nivel da capability == "CONTROL"?
   -> Pertence ao escopo seguro (restart_service, host pentium, servico allowlisted)?
      SIM:
         -> Cooldown ativo para este servico?
            SIM -> CONFIRM (desarme de circuit breaker; solicita operador)
         -> Budget de acoes estourado na janela?
            SIM -> CONFIRM (limite de tentativas; solicita operador)
         -> Todas travas OK:
            -> AUTO (executa automaticamente)
      NAO:
         -> Control genericamente permitido com confirmacao?
            SIM -> CONFIRM (aguarda confirmacao humana)
            NAO -> DENY

4. Nivel da capability == "SYSTEM" ou "CRITICAL"?
   -> CONFIRM se o operador confirmou explicitamente, senao CONFIRM (aguarda confirmacao).
```

## Contrato de Integração

O `CognitiveDaemon` injeta o `SafeLocalCapabilityExecutor` configurado com:
- `host: "pentium"`
- `services: ("atlas-observation.service", "atlas-dashboard.service")`
- `runner`: executor subprocess bounded
- `verifier`: callback de verificação pós-ação

Toda ação executada ou bloqueada gera entrada em `dashboard-events.jsonl` e é refletida no `ActionPlanStore`.
