# Design de Arquitetura — Atlas SSH-Only

## Decisão

A partir de 2026-09-05, o Atlas deixa de usar Agente de Nó próprio e transporte multiprotocolo entre Pentium e os demais nós do homelab.

O Atlas permanece centralizado no `pentium`. `core`, `x99` e futuros nós administrados são acessados remotamente por SSH autenticado, preferencialmente sobre Tailscale.

Esta decisão substitui as partes A5, A6, A7 e A8 do design `2026-09-04-atlas-motor-estado-afetivo-design.md` que dependiam de um agente C++ distribuído. O histórico anterior permanece preservado para rastreabilidade.

## Motivação

O Agente de Nó adicionou uma superfície operacional e de build desproporcional ao objetivo atual do Atlas: C++/CMake, CI cross-platform, TLS próprio, gRPC/Protobuf e múltiplos canais de transporte.

O homelab já possui um canal administrativo adequado para a função necessária: SSH, com alcance protegido por Tailscale e autenticação por chave.

A arquitetura passa a priorizar simplicidade operacional, observabilidade explícita e menor custo de manutenção sem relaxar as regras de segurança.

## Princípios preservados

1. estado técnico continua determinístico e autoritativo;
2. estado afetivo nunca reclassifica saúde técnica;
3. LLM nunca recebe shell arbitrário nem autoridade direta sobre infraestrutura;
4. observação, diagnóstico e execução são bounded;
5. operações sensíveis continuam sujeitas a política e autorização explícita;
6. nenhuma credencial ou chave privada é versionada.

## Arquitetura alvo

```text
Pentium / Atlas
  |-- Observation Runtime
  |-- Health / Perception / Correlation
  |-- Affective Engine
  |-- SSH Remote Operations
  |     |-- inventory/policy
  |     |-- command catalog READ-only
  |     |-- timeout/retry/backoff/concurrency bounds
  |     `-- result normalizer
  |-- future Cognitive Context / LLM
  `-- future Reaction / Audio / Voice

          SSH sobre Tailscale
             |          |
             v          v
            Core       x99
```

Não existe daemon Atlas nos nós remotos. Também não existe porta, protocolo ou heartbeat Atlas próprio.

O Pentium coleta evidências sob demanda ou por polling controlado usando operações SSH previamente cadastradas. Cada operação possui identidade estável e implementação por sistema operacional quando necessário.

## Fronteira SSH

A API interna não expõe `run_shell(command: str)` nem equivalente. Ela recebe uma intenção técnica enumerada e parâmetros validados.

Operações iniciais previstas:

- `LER_USO_DISCO`;
- `LER_MEMORIA`;
- `LER_CPU`;
- `LER_UPTIME`;
- `LER_SERVICO`;
- `LER_PROCESSOS_RESUMIDOS`;
- `LER_REDE_RESUMIDA`;
- `LER_TEMPERATURA` quando suportado.

Cada intenção mapeia para comando fixo ou template fechado. Parâmetros não podem alterar a estrutura do comando nem introduzir operadores de shell.

Resultados remotos são reduzidos a estruturas pequenas antes de entrarem no domínio do Atlas. Logs brutos, dumps e saídas ilimitadas não são propagados para o motor afetivo ou futura LLM.

## Política operacional

Operações são classificadas em três níveis:

- `READ`: observação e diagnóstico sem alteração de estado; podem ser automatizadas dentro de orçamento definido;
- `CONTROL`: altera estado operacional, por exemplo reiniciar serviço; exige autorização explícita separada;
- `DESTRUCTIVE`: reboot, poweroff, alteração de firewall, rota, DNS, SSH, Tailscale, armazenamento ou operações equivalentes; exige autorização explícita específica e permanece fora da primeira implementação.

A primeira implementação SSH é exclusivamente `READ`.

Toda chamada possui timeout, limite de saída, limite de tentativas, backoff, cooldown por entidade e limite de concorrência. Falha SSH é evidência de percepção, não prova isolada de falha do host.

## Identidade e confiança

O inventário define host lógico, endereço Tailscale ou hostname autorizado, usuário remoto, plataforma esperada e conjunto de operações permitidas.

A política de host key é estrita. Mudança inesperada de chave interrompe a operação e produz evidência de segurança; não existe aceitação automática de nova host key.

Autenticação é por chave SSH administrada fora do repositório. Senhas, chaves privadas e material secreto nunca entram em configuração versionada, journal ou contexto cognitivo.

## Integração com Observation Runtime

O Observation Runtime existente continua sendo o orquestrador de coleta. Novas `StimulusSource` SSH devem produzir snapshots reduzidos e determinísticos e reutilizar deduplicação, timeout, backoff, journal e `StimulusBus` já existentes.

A coleta local do Pentium permanece local. SSH é usado somente para entidades remotas ou quando uma evidência remota é explicitamente necessária.

## Impacto no roadmap

As slices A1–A4 permanecem válidas.

As slices anteriores passam ao seguinte estado:

- `A5 — Agente de Nó Atlas`: descontinuada como arquitetura alvo; o código já presente no baseline v0.1.0 permanece apenas por rastreabilidade e não será implantado/promovido operacionalmente;
- `A6 — Transporte multiprotocolo`: cancelada; TCP/TLS próprio, gRPC/mTLS e HTTPS/mTLS deixam de fazer parte do Atlas;
- `A7 — Diagnóstico Ativo`: substituída por `S1 — SSH Remote Operations READ-only`;
- `A8 — Integração e Certificação`: substituída por `S2 — SSH Observation Integration & Certification`.

Após S1 e S2, o roadmap cognitivo continua:

`S1 -> S2 -> C1 Contexto Cognitivo bounded -> C2 LLM Gateway -> C3 Reaction Loop -> C4 Policy/Fallback -> C5 Certificação E2E`.

## S1 — SSH Remote Operations READ-only

Objetivo: criar a fronteira SSH segura e testável sem integrá-la ainda a decisões cognitivas.

DoD mínimo:

- inventário explícito de nós autorizados;
- catálogo fechado de operações READ;
- execução SSH com host-key checking estrito;
- timeouts, output bounds, retry/backoff e concorrência limitados;
- normalização determinística de resultados;
- zero shell arbitrário e zero operação CONTROL/DESTRUCTIVE;
- testes com transporte injetável/fake e integração SSH controlada;
- CI GREEN no HEAD exato.

## S2 — SSH Observation Integration & Certification

Objetivo: ligar S1 ao Observation Runtime e certificar a leitura real de Pentium/Core/x99 sem alterar os nós.

A certificação física é READ-only e só ocorre após testes e CI GREEN. Nenhum serviço persistente novo é instalado em Core ou x99.

## Estratégia de testes

S1 deve ser testada sem depender dos equipamentos reais para sua suíte principal.

Cenários mínimos:

- operação READ válida produz resultado normalizado;
- host não autorizado é rejeitado;
- operação não cadastrada é rejeitada;
- parâmetro inválido não alcança o transporte;
- timeout interrompe a operação;
- saída acima do limite é truncada/rejeitada conforme contrato;
- retry respeita orçamento e backoff;
- host key divergente falha fechado;
- falhas de um nó não bloqueiam os demais;
- nenhuma API pública aceita comando shell arbitrário.

S2 adiciona integração com Observation Runtime, deduplicação, recuperação, falha parcial, bounded polling e certificação física READ-only.

## Critérios de conclusão da nova fundação remota

A substituição do Agente de Nó estará concluída quando S1 e S2 estiverem certificadas no mesmo modelo de governança do projeto: implementação orientada por testes, CI GREEN no HEAD exato, evidência física quando aplicável, checkpoint e as-built.

O sucesso não depende de portar o código C++ existente. O A5 já mergeado permanece como legado histórico até uma remoção segura em mudança própria; o A6 não mergeado é descartado e não vira dívida obrigatória de migração.

## Fora de escopo

- agente ou daemon Atlas em Core/x99;
- gRPC, Protobuf ou protocolo de transporte Atlas próprio;
- instalação automática de chaves ou alteração de `sshd`;
- alteração automática de Tailscale;
- shell arbitrário para usuário ou LLM;
- CONTROL/DESTRUCTIVE na primeira implementação;
- auto-remediação;
- LLM, voz, TTS, STT, áudio e memes nesta mudança arquitetural.
