# Atlas Cognitive LLM Reaction Loop — Design

## Decisão

O Atlas permanece sendo o sistema completo de percepção, estado técnico, estado afetivo, foco, memória operacional, expressão e interação do DevEx HomeLab. A mini LLM é o módulo cognitivo-linguístico do Atlas, não sua autoridade técnica nem afetiva.

A integração cognitiva será implementada em cinco slices, preservando o roadmap vigente da Issue #20:

`C1 Contexto Cognitivo bounded -> C2 LLM Gateway -> C3 Reaction Loop -> C4 Policy/Fallback -> C5 Certificação E2E`

A primeira slice executável é C1. Nenhuma slice posterior será antecipada por implementação parcial dentro de C1.

## Objetivos

1. transformar estado já normalizado em contexto cognitivo pequeno, estável e auditável;
2. permitir que uma mini LLM local interprete o ambiente sem receber telemetria bruta;
3. acionar a LLM apenas quando houver motivo cognitivo explícito;
4. produzir resposta estruturada, sem side effects operacionais na primeira promoção;
5. preservar operação 24/7 do Atlas mesmo quando a LLM estiver indisponível;
6. manter o Pentium dentro de orçamento de CPU, RAM, swap, temperatura e latência.

## Não objetivos

- substituir `ObservationRuntime`, Health Engine, correlação ou Motor Afetivo;
- permitir shell, SSH arbitrário ou comando textual livre;
- permitir que a LLM altere saúde técnica, estado afetivo, vínculos, allowlists ou privilégios;
- incluir STT, TTS, reconhecimento de identidade ou avatar nesta iniciativa;
- executar `CONTROL` ou `DESTRUCTIVE` antes de C4/C5 e das policies correspondentes.
## Arquitetura

```text
Discovery / Managed READ / fontes locais
                |
                v
        ObservationRuntime
                |
                v
     Percepcao / Correlacao
                |
                v
         Motor Afetivo
                |
                v
    ContextoCognitivoBuilder   <- C1
                |
         ActivationPolicy      <- C1
                |
                v
          LLM Gateway          <- C2
                |
                v
        LLM Reaction Loop      <- C3
                |
                v
       RespostaCognitiva
                |
         Policy / Fallback     <- C4
                |
                v
     Audio / Avatar / Acoes
                |
        Certificacao E2E       <- C5
```

A LLM não controla o loop de observação. Ela é consumidora eventual de contexto derivado e bounded.
## C1 — Contexto Cognitivo bounded

`ContextoCognitivo` é um snapshot reduzido e serializável, construído somente a partir de contratos já autoritativos.

Campos mínimos:

- `motivo_ativacao`;
- `entidade_principal`;
- `estado_tecnico`;
- `estado_percepcao`;
- `incidente_principal` opcional;
- `estado_afetivo` resumido;
- `emocao_principal` e nuances limitadas;
- `foco_atencao`;
- `expectativa` relevante opcional;
- `mudancas_recentes` com máximo configurável;
- `dependencias_afetadas` resumidas com máximo configurável;
- `timestamp`;
- `versao_schema`.

O builder nunca consulta rede, executa probes ou lê logs brutos. Ele recebe estruturas já normalizadas e apenas reduz/compõe informação.

### Bounds de C1

- nenhuma lista ilimitada;
- nenhum log/dump/série temporal bruta;
- strings possuem tamanho máximo configurado;
- mapas desconhecidos são rejeitados ou reduzidos por schema explícito;
- payload final possui limite de bytes antes de C2 existir;
- truncamento é explícito e auditável, nunca silencioso em campo crítico.
## ActivationPolicy

A política de ativação é determinística e pertence a C1. Ela decide se existe motivo suficiente para solicitar cognição, mas não executa a LLM.

Motivos iniciais permitidos:

- criticidade técnica relevante;
- novidade acima de threshold;
- mudança relevante de estado/percepção;
- mudança afetiva significativa;
- recuperação importante;
- expectativa quebrada;
- interação humana;
- reflexão periódica explicitamente configurada.

A política possui cooldown, deduplicação e orçamento temporal. Eventos repetidos equivalentes não geram ativações ilimitadas.

Mudanças afetivas pequenas continuam sendo processadas por A1–A4 sem ativação cognitiva.

## C2 — LLM Gateway

C2 encapsula o backend local de inferência. O candidato inicial permanece `Qwen3-0.6B` GGUF Q4 via `llama.cpp`, condicionado a benchmark físico.

O gateway recebe apenas `ContextoCognitivo` validado e uma instrução de tarefa versionada. Ele não recebe shell, ambiente, arquivos arbitrários, URLs, secrets ou acesso direto à rede.

O backend deve ser substituível sem alterar C1, C3 ou o Motor Afetivo.
## C3 — LLM Reaction Loop

C3 recebe uma ativação aprovada por C1, solicita inferência por C2 e normaliza a saída para `RespostaCognitiva`.

Campos conceituais de `RespostaCognitiva`:

- `texto` opcional;
- `resumo` opcional;
- `intencao` opcional;
- `parametros_intencao` tipados;
- `confianca` limitada a `0.0..1.0`;
- `motivo`;
- `requer_confirmacao`;
- `timestamp`;
- `versao_schema`.

Saída inválida, incompleta ou fora do schema nunca vira ação. O loop registra erro e retorna fallback estruturado.

C3 não altera `EstadoAfetivo`, `EstadoPercepcao`, `TechnicalState` nem enrollment.

## C4 — Policy e Fallback

C4 valida intenções contra catálogo fechado. A LLM só pode escolher entre capacidades previamente registradas e parâmetros validados.

Não existe `run_shell`, `ssh(command)`, comando textual livre ou expansão dinâmica de allowlist.

Categorias:

- `READ`: pode ser autorizada automaticamente por policy explícita;
- `CONTROL`: exige policy e autorização conforme contrato vigente;
- `DESTRUCTIVE`: exige confirmação humana independente da LLM.

Falha ou timeout da LLM nunca bloqueia Health, Observation Runtime, Motor Afetivo, áudio canônico crítico ou operação básica do control plane.
## C5 — Certificação E2E

C5 certifica o caminho completo no Pentium sem conceder autoridade além das policies aprovadas.

A certificação deve medir:

- RSS da LLM e do processo Atlas;
- uso de swap;
- CPU em repouso e durante inferência;
- temperatura antes, durante e após inferência;
- tempo até primeiro token/resposta;
- tokens por segundo quando exposto pelo backend;
- latência total de ativação -> `RespostaCognitiva`;
- comportamento sob timeout/falha do backend;
- preservação do Observation Runtime sob carga cognitiva;
- ausência de fila ilimitada de ativações.

A promoção para serviço permanente depende de orçamento físico observado. Não há meta numérica inventada antes do benchmark do hardware real.

## Memória e journal

C1–C5 reutilizam journals existentes como evidência, mas não introduzem memória episódica de longo prazo nesta iniciativa.

O journal cognitivo registra somente metadados bounded: motivo de ativação, fingerprint/context id, backend/modelo, duração, status, intenção produzida e fallback. Prompt completo, secrets, dumps e telemetria bruta não são persistidos por padrão.

## Relação com áudio e avatar

A LLM pode produzir linguagem humana e intenção semântica, mas não escolhe emoção, gesto ou severidade técnica.

Audio Engine continua consumindo decisões de reação canônicas. Avatar continua consumindo `EstadoVisualAtlas` derivado do Motor Afetivo e foco resolvido. Integração de fala/TTS é iniciativa posterior.

## Falhas e isolamento

- backend ausente -> Atlas continua determinístico e registra indisponibilidade cognitiva;
- timeout -> inferência é abortada dentro do budget e não bloqueia observação;
- resposta inválida -> rejeição por schema + fallback;
- contexto inválido -> C1 falha fechado antes da LLM;
- pressão de recursos -> novas ativações podem ser suprimidas por policy bounded;
- reinício -> contexto é reconstruído do estado atual; saída antiga da LLM não vira verdade presente.
## Estratégia de testes

### C1

- construção determinística do `ContextoCognitivo`;
- limites de tamanho/listas/strings;
- rejeição de campo não permitido;
- truncamento explícito;
- ActivationPolicy por motivo;
- cooldown, deduplicação e orçamento de ativações;
- nenhuma chamada de LLM.

### C2

- backend fake e adapter `llama.cpp` testável;
- timeout e cancelamento;
- modelo ausente/incompatível;
- limite de contexto;
- nenhuma rede/shell arbitrário.

### C3/C4

- parsing/schema de `RespostaCognitiva`;
- intenção desconhecida rejeitada;
- parâmetros inválidos rejeitados;
- fallback em saída malformada;
- READ/CONTROL/DESTRUCTIVE respeitam policy;
- nenhuma alteração direta em estado técnico/afetivo.

### C5

- testes físicos somente após suíte local e CI GREEN no HEAD exato;
- benchmark no Pentium real;
- falha da LLM não interrompe observação/reação determinística;
- evidência, checkpoint e as-built do mesmo SHA.

## Ordem de implementação

1. C1 — Contexto Cognitivo bounded + ActivationPolicy;
2. C2 — LLM Gateway;
3. C3 — Reaction Loop;
4. C4 — Policy/Fallback;
5. C5 — Certificação E2E.

Cada slice recebe TDD, PR/checkpoint e CI no HEAD exato. Nenhuma evidência de SHA anterior promove a próxima slice.

## Critério de conclusão

A iniciativa cognitiva termina quando C1–C5 estiverem implementadas e certificadas, a mini LLM operar dentro do orçamento físico do Pentium e sua indisponibilidade não comprometer o Atlas determinístico.

A primeira slice C1 termina quando o contrato de `ContextoCognitivo` e a `ActivationPolicy` estiverem implementados por TDD, bounded, sem inferência real, com toda a suíte GREEN e Foundation CI GREEN no HEAD exato.

## Compatibilidade com arquitetura vigente

A1–A4 permanecem autoritativas para estado afetivo. D1/D2 e futuras M1/M2/I1 continuam responsáveis por percepção e capacidades gerenciadas. A5 distribuída é legado histórico e A6 multiprotocolo continua cancelada.

Esta especificação não reintroduz agente distribuído, gRPC/Protobuf, protocolo remoto Atlas ou shell para a LLM.