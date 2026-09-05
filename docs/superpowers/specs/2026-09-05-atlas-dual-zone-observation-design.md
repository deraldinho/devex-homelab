# Atlas Dual-Zone Observation & Control — Design

## Decisão

O `pentium` permanece como cérebro central do Atlas e possui duas interfaces de rede com papéis distintos.

A interface Wi-Fi ligada diretamente ao roteador da operadora pertence à zona `WIFI_OBSERVED`. Nela o Atlas mantém descoberta contínua e bounded de equipamentos presentes na mesma rede local, usando ARP como mecanismo mínimo obrigatório para IPv4. Essa zona é de observação: descobrir um dispositivo não concede qualquer privilégio administrativo.

A interface ligada ao firewall pertence à zona `MANAGED`. Nela os hosts administrados pelo DevEx HomeLab são observados e operados principalmente por SSH autenticado.

O Atlas não usa Agente de Nó distribuído, daemon próprio, gRPC/Protobuf ou protocolo remoto Atlas.

Esta especificação substitui o desenho anterior `Atlas SSH-Only`: SSH deixa de ser mecanismo de descoberta e passa a ser o principal adapter de observação profunda e controle da zona gerenciada.

## Objetivos

1. saber continuamente quais equipamentos estão presentes no Wi-Fi da operadora;
2. transformar presença de rede em entidades estáveis do inventário Atlas;
3. observar profundamente máquinas da rede interna sem instalar agente Atlas;
4. permitir ações administrativas tipadas via SSH na zona gerenciada;
5. alimentar o `ObservationRuntime`, percepção, motor afetivo e futura LLM com estado estruturado;
6. manter todo polling, probing, output, retry e concorrência bounded.

## Arquitetura

```text
                         PENTIUM / ATLAS
                               |
                +--------------+--------------+
                |                             |
        WIFI_OBSERVED                    MANAGED
      Wi-Fi da operadora              rede do firewall
                |                             |
        ARP Discovery                  Managed Inventory
        Neighbor Cache                       + SSH
                |                             |
        Presence Registry              Remote Operations
                |                    READ / CONTROL policy
                +--------------+--------------+
                               |
                      ObservationRuntime
                               |
                Health / Perception / Correlation
                               |
                        Affective Engine
                               |
                   future Cognitive Context / LLM
```

O `ObservationRuntime` existente continua sendo o único scheduler de observação. Novas fontes devem implementar `StimulusSource`, produzir `SourceSnapshot` reduzido e reutilizar timeout, backoff, jitter, deduplicação, journal e `StimulusBus` já existentes.

Nenhuma fonte nova cria loop infinito próprio quando o runtime já puder agendá-la.

## Zona `WIFI_OBSERVED`

Objetivo: responder continuamente “quais equipamentos estão presentes neste Wi-Fi?” sem assumir autorização administrativa sobre eles.

A fonte de descoberta deve operar somente na interface Wi-Fi configurada. O escopo da varredura é derivado da rede IPv4 efetivamente configurada nessa interface; nunca deve atravessar gateway, firewall ou outra interface.

O mecanismo mínimo é:

- leitura da tabela de vizinhos/ARP local;
- ARP sweep bounded da sub-rede diretamente conectada;
- correlação dos resultados por MAC e IP;
- janela de presença com `first_seen`, `last_seen` e estado atual;
- emissão apenas de mudanças relevantes para o `StimulusBus`.

O intervalo é configurável. O valor inicial de referência é 60 segundos, com jitter pequeno fornecido pelo próprio `ObservationRuntime`; não é requisito de protocolo e pode ser ajustado por configuração e certificação física.

A fonte não faz port scan amplo, brute force, login, exploit, alteração de configuração ou tentativa automática de SSH nessa zona.

IPv6/NDP é extensão planejada após a certificação IPv4/ARP e não bloqueia a primeira slice.

### Registro de presença

Cada dispositivo descoberto deve produzir uma identidade de observação com, no mínimo: `mac`, `ipv4`, `first_seen`, `last_seen`, `presence` e `zone`.

Quando disponível de fontes locais seguras, podem ser anexados `hostname` e fabricante provável do OUI. Essas informações são pistas, não identidade criptográfica.

## Zona `MANAGED`

Objetivo: observar profundamente e executar operações administrativas autorizadas em hosts pertencentes ao homelab atrás do firewall.

Regra de onboarding: todo novo host Linux/Windows que deva ser classificado como `MANAGED` precisa oferecer um canal SSH autenticado acessível pelo Pentium. Equipamentos que não suportem SSH podem receber outro adapter autorizado em mudança futura, mas não são promovidos automaticamente a `MANAGED` por terem sido descobertos.

O inventário gerenciado registra identidade lógica, endereço autorizado, usuário remoto, plataforma, host key esperada e operações permitidas. Credenciais e chaves privadas permanecem fora do repositório.

Host-key checking é estrito. Mudança inesperada de host key falha fechado e gera evidência de segurança; o Atlas não aceita automaticamente a chave nova.

### Operações READ

O catálogo inicial inclui observação tipada de CPU, memória, disco, uptime, temperatura quando suportada, estado de serviços, processos resumidos, rede resumida, containers e logs resumidos quando explicitamente cadastrados.

Resultados remotos são normalizados e limitados antes de entrar no domínio. Saída bruta ilimitada nunca é propagada ao motor afetivo ou futura LLM.

### Operações CONTROL

A arquitetura suporta operações allowlisted como `START_SERVICE`, `STOP_SERVICE`, `RESTART_SERVICE` e `REBOOT_HOST`.

A API interna recebe intenção estruturada; não existe `run_shell(command: str)` público para LLM ou usuário de alto nível.

Por padrão, `CONTROL` exige autorização explícita para a ação. Uma política futura pode pré-autorizar combinações exatas de host + operação + alvo, mas essa autorização deve ser configurada fora da decisão da LLM e auditável.

## Estados de entidade

Dispositivos seguem uma máquina de estados independente da saúde técnica:

`NEW -> DISCOVERED -> IDENTIFIED -> ENROLLED -> MANAGED`

- `NEW`: presença observada pela primeira vez;
- `DISCOVERED`: MAC/IP correlacionados e persistidos;
- `IDENTIFIED`: entidade conhecida ou classificada com confiança suficiente;
- `ENROLLED`: canal administrativo autorizado e identidade verificada;
- `MANAGED`: participa da observação profunda e pode receber operações permitidas.

Um dispositivo do Wi-Fi pode permanecer indefinidamente em `DISCOVERED` ou `IDENTIFIED`. Descoberta nunca promove automaticamente para `ENROLLED` ou `MANAGED`.

Saúde técnica (`healthy`, `degraded`, `critical` etc.) continua separada do estado de enrollment.

## Fluxo de dados

1. fonte ARP ou adapter SSH coleta evidência bounded;
2. coletor normaliza para estrutura pequena e determinística;
3. `StimulusSource.poll()` produz `SourceSnapshot`;
4. `ObservationRuntime` aplica timeout, schedule, backoff, jitter e deduplicação;
5. `StimulusBus` recebe somente mudanças relevantes;
6. percepção/correlação resolve entidade, estado e novidade;
7. motor afetivo recebe interpretação derivada sem poder reclassificar a saúde técnica;
8. futura LLM recebe contexto estruturado e nunca saída de shell irrestrita.

## Falhas e limites

Falha de ARP discovery significa perda ou degradação da capacidade de observação daquela interface; não prova que todos os dispositivos desapareceram.

Ausência de um dispositivo só vira evento de desaparecimento depois da janela configurada de presença. Uma única varredura sem resposta não é suficiente.

Falha SSH é evidência sobre o canal administrativo, não prova isolada de falha do host. Outras evidências podem manter o host tecnicamente alcançável.

Toda operação deve ter:

- timeout explícito;
- limite de saída;
- limite de tentativas;
- backoff bounded;
- jitter quando agendada;
- limite de concorrência;
- cooldown de falha/evento;
- nenhuma fila ilimitada.

O Pentium deve continuar funcional com 3 GB de RAM. A descoberta não mantém uma conexão permanente por dispositivo; coleta ARP é periódica e conexões SSH são abertas sob demanda ou reaproveitadas somente dentro de limites explícitos.

## Segurança e confiança

`WIFI_OBSERVED` é uma zona não administrativa. Nenhum dispositivo nela ganha privilégios por aparecer na rede.

`MANAGED` é uma zona administrativa. A origem Pentium, host key, identidade lógica e operação allowlisted precisam ser verificadas antes de execução.

A LLM pode sugerir uma intenção, mas não pode criar comando shell, alterar allowlist, aceitar host key, instalar chave, mudar firewall/rota/DNS/SSH/Tailscale ou ampliar sua própria autoridade.

## Roadmap revisado

A1–A4 permanecem válidas. A5 deixa de ser arquitetura alvo e permanece apenas como legado histórico até remoção segura em mudança própria. A6 continua cancelada.

A nova linha é:

`D1 Network Discovery -> D2 Identity & Presence Registry -> M1 Managed SSH READ -> M2 Managed CONTROL -> I1 Observation Integration -> C1 -> C2 -> C3 -> C4 -> C5`

### D1 — Network Discovery

Implementar descoberta ARP IPv4 bounded exclusivamente na interface Wi-Fi da operadora, com testes de escopo, deduplicação, janela de presença e integração mínima ao `ObservationRuntime`.

### D2 — Identity & Presence Registry

Persistir e correlacionar MAC/IP/hostname/vendor/first_seen/last_seen, impedir duplicação por troca de IP e produzir eventos `appeared`, `changed`, `missing` e `recovered`.

### M1 — Managed SSH READ

Generalizar o transporte SSH já existente para inventário de hosts e catálogo READ tipado, com host-key checking estrito, normalização e bounds.

### M2 — Managed CONTROL

Adicionar intents administrativas allowlisted para serviço e reboot, com autorização explícita por padrão, auditoria e nenhuma API de shell arbitrário.

### I1 — Observation Integration & Certification

Certificar as duas zonas simultaneamente no Pentium: descoberta contínua no Wi-Fi e observação/controle seguro dos hosts internos, sem que falha de uma zona bloqueie a outra.

## Estratégia de testes

D1 deve possuir fake de neighbor table/ARP probe e testes sem depender da rede física para a suíte principal.

Cenários mínimos de D1/D2:

- interface errada é rejeitada;
- endereço fora da sub-rede diretamente conectada nunca é sondado;
- dispositivo novo gera `appeared` uma única vez;
- resposta repetida é deduplicada;
- mudança de IP para o mesmo MAC não cria entidade duplicada;
- ausência de uma única rodada não marca dispositivo como `missing`;
- expiração da janela produz `missing`;
- reaparecimento produz `recovered`;
- falha do coletor gera degradação da fonte sem declarar todos os hosts offline;
- número de probes, tamanho de snapshot e concorrência respeitam bounds.

Cenários mínimos de M1/M2:

- host desconhecido é rejeitado;
- host key divergente falha fechado;
- operação fora do catálogo é rejeitada;
- parâmetro inválido não alcança o transporte;
- READ retorna estrutura bounded;
- CONTROL sem autorização é rejeitado;
- combinação previamente autorizada executa somente o comando fixo correspondente;
- timeout/falha SSH não bloqueia outros hosts nem a descoberta Wi-Fi;
- nenhuma API pública aceita comando shell arbitrário.

## Fora de escopo inicial

IPv6/NDP, SNMP, descoberta via API do roteador, port scan amplo, instalação automática de SSH, distribuição automática de chaves, auto-remediação, alteração de firewall/rota/DNS/Tailscale e decisão autônoma da LLM sobre privilégios ficam fora das primeiras slices.

## Critério de conclusão

A fundação dual-zone está concluída quando D1, D2, M1, M2 e I1 estiverem implementadas por TDD, com CI GREEN no HEAD exato, certificação física controlada no Pentium, checkpoint e as-built. Nenhuma evidência de SHA anterior pode substituir a certificação do HEAD vigente.
