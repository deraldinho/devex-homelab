# Atlas Local Intelligence — Design de Domínio

## 1. Papel no DevEx HomeLab

O **Atlas** é a camada local de percepção e interação do DevEx HomeLab. Ele roda no `pentium` (`homelab.control`) e transforma observed state técnico em um estado global compreensível, reações sonoras e, em fases posteriores, interação por voz e linguagem natural.

O Atlas não substitui o Pentium Agent, o heartbeat, o Tailscale, o MikroTik nem os contratos de observabilidade existentes. Ele **consome** esses contratos e adiciona interpretação e interação acima deles.

## 2. Princípios

1. **Estado técnico é determinístico.** Uma LLM nunca decide se um nó está saudável, crítico ou autorizado a executar uma ação.
2. **Sem shell arbitrário.** A camada de linguagem produz intents estruturadas; somente o Policy/Action Engine pode resolver intents para ações allowlisted.
3. **Local-first.** Health, reactions e comandos básicos devem continuar funcionando sem Internet.
4. **Baixo orçamento de recursos.** O Pentium é Pentium Dual-Core T4300, 2C/2T, ~2,5 GiB RAM e ~2,8 GiB swap; a plataforma deve preservar o papel 24/7 de control plane.
5. **Expressão separada de severidade.** Um meme pode expressar emoção, mas nunca substitui um alerta técnico inequívoco.
6. **Sem repetição excessiva.** Cooldown, histerese, anti-repeat e quiet hours são parte do contrato, não detalhes cosméticos.
7. **Vocabulário semântico é interno.** Nenhum serviço externo depende do vocabulário, códigos ou registry semântico do Atlas; a tradução pertence à fronteira de percepção do Atlas.

## 3. Componentes

A fronteira S1 preserva ownership dos contratos externos:

```text
contrato externo -> StimulusSource -> Stimulus -> FronteiraSemantica -> EventoSemantico
```

`FronteiraSemantica` é interna ao Atlas. Serviços observados continuam publicando seus próprios contratos e nunca precisam traduzir ou armazenar códigos cognitivos do Atlas.

### Fast Router S2

`EventoSemantico` entra no `FastRouter` determinístico antes de qualquer caminho lento. A decisão pode abrir lanes `FAST_REACTION`, `AFFECT`, `CACHE_LOOKUP` e `SLOW_LLM`; `DROP` é exclusivo.

Eventos críticos e recuperações relevantes seguem o fast path sem aguardar LLM. `SLOW_LLM` é apenas deferência assíncrona para eventos novos na faixa ambígua; eventos conhecidos de baixa novidade preferem cache.

```text
Observed State
  |-- management-network health
  |-- Pentium heartbeat
  |-- Pentium Agent actions
  |-- MikroTik / Internet / DNS adapters (futuro)
  |-- runners/jobs/services (futuro)
  v
Health Engine
  v
Global State + intensity + reasons
  |
  +--> Event Journal
  |
  +--> Reaction Engine
  |      |-- canonical sound category
  |      |-- optional meme category
  |      `-- cooldown/rarity/anti-repeat
  |              v
  |          Audio Engine
  |
  `--> Voice/LLM path (fases posteriores)
         microphone -> wake/VAD -> STT -> Qwen -> intent
                                      -> Policy -> allowlisted Action Engine
                                      -> TTS/response
```

## 4. Estados técnicos canônicos

- `healthy`: componentes obrigatórios saudáveis e sem pressão relevante;
- `active`: atividade presente sem pressão;
- `busy`: carga sustentada, porém dentro do orçamento;
- `degraded`: perda parcial de capacidade, latência/perda ou serviço não crítico degradado;
- `stressed`: recurso ou fila sob pressão sustentada, com risco de degradação;
- `critical`: indisponibilidade de componente obrigatório ou violação crítica;
- `recovered`: transição temporária após retorno de `degraded/stressed/critical` para condição saudável.

A severidade técnica não possui humor. A emoção/expressão é derivada separadamente.

## 5. Expressão, linguagem sonora e Matriz Afetiva Expandida

A comunicação normal usa uma linguagem sonora tecnológica própria acompanhada de uma **Matriz Afetiva de 20 Sentimentos Canônicos** calculada deterministicamente a partir de métricas do cluster (`ativação`, `valência`, `estresse`, `novidade`, `gravidade`, `urgência`):

- `sereno`, `calmo`, `focado`, `curioso`, `empolgado`;
- `vigilante`, `apreensivo`, `sobrecarregado`, `exausto`, `aliviado`;
- `confiante`, `hesitante`, `cauteloso`, `frustrado`, `satisfeito`;
- `intrigado`, `protetor`, `solitário`, `paciente`, `resoluto`.

Cada categoria sonora possui um **pool** de múltiplos sons em PCM 16-bit 44.1kHz mono. O Reaction Engine escolhe entre variantes com pesos, memória recente, raridade e cooldown. Em evento crítico, o som canônico de criticidade sempre precede ou substitui qualquer meme.

## 6. Intensidade

A intensidade é um inteiro de `0..4` calculado por regras determinísticas:

- `0`: neutro;
- `1`: reação discreta;
- `2`: perceptível;
- `3`: forte;
- `4`: crítico/especial.

Thresholds específicos ficam em configuração versionada e exigem duração mínima/histerese para evitar oscilações.

## 7. Cérebro Cognitivo de Background (Hermes 3)

O cérebro cognitivo do Atlas opera com **Hermes 3** (`hermes-3-llama-3.1-8b`), executado em background desconectado do caminho crítico da observação sensorial.

A inferência opera sob um **Governador Afetivo Total**: o tom de voz, ritmo e cadência da resposta refletem a emoção ativa calculada deterministicamente pela infraestrutura.

A LLM fica fora do caminho crítico de percepção, emoção e reação imediata. Eventos semânticos e decisões Fast Path continuam funcionando mesmo quando a LLM está lenta, indisponível ou em timeout.

A LLM tem quatro funções permitidas:

1. interpretar linguagem humana para intent estruturada allowlisted;
2. resumir observed state/event journal com propriocepção biomecânica;
3. formular resposta humana no Discord e painéis com inteligência emocional;
4. deliberar hipóteses de diagnóstico técnico sob demanda do operador.

Ela não recebe autoridade para avaliar gates técnicos, construir shell arbitrário ou executar ações não allowlisted. Toda capability acionada passa por validação estrita de política.

## 8. Voz

A trilha de voz será local-first:

`wake word -> VAD -> STT -> intent -> policy -> resposta -> TTS`.

A primeira promoção de voz será READ-only. Ações `CONTROL` só entram após allowlist explícita; ações `DESTRUCTIVE` exigem confirmação humana independente da LLM.

## 9. Modos de expressão

- `quiet`: apenas eventos importantes;
- `normal`: linguagem Atlas e memes raros;
- `expressive`: maior variedade e emoção;
- `chaos`: maior chance de reações especiais, sem alterar regras técnicas nem permissões.

## 10. Fases

1. Atlas State & Reaction Foundation;
2. Audio Engine e biblioteca local;
3. integração com MikroTik/Internet/DNS e runners;
4. benchmark e promoção da mini LLM;
5. voice input READ-only;
6. TTS;
7. Action Engine allowlisted;
8. journal consultável e resumo de histórico;
9. certificação física e as-built.

## 11. Limites da primeira slice

A primeira slice não instala LLM, STT, TTS, não baixa memes e não altera rede. Ela cria o modelo de estado global, o Reaction Engine, o journal e o contrato de biblioteca sonora, consumindo contratos já versionados sempre que possível.

### Fast Dispatch S3

A S3 conecta `DecisaoFastRouter` a um `FastDispatcher` tipado e bounded. O dispatcher preserva a ordem das lanes e delega cada entrega por porta explícita, sem recalcular score, health, severidade ou autorização.

`FAST_REACTION`, `AFFECT` e `CACHE_LOOKUP` são entregues aos respectivos owners. Falha em uma lane é registrada sem cancelar lanes independentes seguintes. `DROP` continua exclusivo e não chama nenhuma porta.

`SLOW_LLM apenas agenda` uma intenção tipada em fila bounded para processamento posterior. A S3 não importa nem executa `llm_gateway` ou `ReactionLoopCognitivo` inline, mantendo inferência fora do caminho crítico.

### Managed SSH READ M1

A M1 generaliza o transporte SSH existente do Pentium para observacao profunda de hosts explicitamente `MANAGED`. O inventario gerenciado resolve `host_id`, identidade SSH, `known_hosts`, plataforma, bounds e allowlist READ antes de qualquer chamada remota.

O contrato de transporte usa `BatchMode=yes`, `IdentitiesOnly=yes`, `StrictHostKeyChecking=yes` e `UserKnownHostsFile` explicito. Mudanca inesperada de host key falha fechado; descoberta de rede nunca promove um equipamento para MANAGED.

O `ManagedReadService` expõe somente operacoes tipadas (`cpu`, `memory`, `disk`, `uptime`, `temperature`, `services`, `processes`, `network`, `containers`, `logs`) resolvidas para comandos fixos por plataforma. Nao existe API publica de shell arbitrario.

Saida remota e bounded por host antes de entrar no dominio. Falha SSH ou parsing degrada a evidencia daquele READ sem redefinir a saude tecnica do host. `x99.status` permanece como compatibilidade, agora consumindo a camada tipada M1 em vez de montar comandos SSH diretamente.

M2 CONTROL permanece separada e fora desta slice.

O contrato M1 opera sem shell arbitrario em toda a fronteira de alto nivel.

### Managed CONTROL M2

A M2 adiciona execucao administrativa tipada para hosts `MANAGED` sobre a fundacao SSH M1. `PolicyCapabilities` continua sendo a autoridade: o executor recebe somente uma decisao estruturada e aplica novamente inventario, operacao e alvo em regime default-deny antes de qualquer SSH.

`START_SERVICE`, `STOP_SERVICE` e `RESTART_SERVICE` sao CONTROL. `REBOOT_HOST` permanece DESTRUCTIVE e exige confirmacao humana independente. A autorizacao efetiva e restrita a combinacao exata host + operacao + alvo; nenhum host ou servico e herdado por permissao generica.

O `ManagedControlService` usa comandos fixos por plataforma, host-key estrita, timeout e output bounded herdados da M1. Nao existe API publica de shell arbitrario e nao ha retry autonomo de CONTROL.

Toda execucao autorizada registra `attempt` antes do transporte e `result` depois. Falha de pre-audit bloqueia a operacao; falha SSH e registrada como evidencia degradada do canal sem inventar sucesso.


### Observation Integration I1

A I1 conecta `WIFI_OBSERVED` e `MANAGED` em um unico ObservationRuntime. `WifiPresenceSource` permanece dona da presenca Wi-Fi; `ManagedObservationSource` transforma somente READ tipado e bounded em `SourceSnapshot`.

Falha ARP e falha SSH permanecem independentes. Erro em `wifi.presence` nao cancela `managed.*`, e erro em `managed.*` nao cancela descoberta Wi-Fi. Falha SSH descreve o canal administrativo e nao declara o host offline.

CONTROL nao participa do polling. O composition root conhece `ManagedReadService`, mas nenhuma fonte de observacao expoe shell ou executor administrativo. A certificacao tecnica I1 exige evidencia simultanea das duas zonas e default-deny de CONTROL; certificacao fisica permanece um gate separado no Pentium.
