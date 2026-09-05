# Design de Implementação — Atlas Motor de Estado Afetivo

## Base e objetivo

- iniciativa: Issue #20 / Atlas Local Intelligence;
- base certificada: PR #23 / Atlas Observation Runtime 24/7;
- base SHA: `1a28a54a051d152d83cf919a7f570e1bacccdf2e`;
- branch de design: `atlas/issue-20-motor-estado-afetivo`;
- host cérebro: `pentium`;
- idioma canônico para novos contratos, documentação, testes e checkpoints: português do Brasil;
- identificadores técnicos novos: português sem acentos quando necessário por compatibilidade.

O objetivo é criar um núcleo afetivo determinístico, persistente e limitado que interprete como acontecimentos técnicos afetam o Atlas sem alterar a verdade técnica. O Pentium continua sendo o cérebro autônomo; Core e x99 são membros vinculados; firewall é órgão vital de comunicação; modem/ONT e link da operadora são dependências externas fortemente vinculadas; projetos podem possuir vínculo afetivo próprio independente do host.

## Decisão arquitetural

Foram considerados três modelos: estados emocionais discretos, vetor contínuo e reconstrução ampla a partir de histórico de eventos. A arquitetura aprovada é híbrida: vetor contínuo como fonte de verdade, com rótulos emocionais derivados deterministicamente. A reconstrução completa por histórico fica fora desta iniciativa por custo e complexidade prematuros.

Princípios:

1. o estado técnico permanece autoritativo;
2. o estado afetivo nunca reclassifica saúde técnica;
3. nenhuma LLM escreve diretamente no estado afetivo;
4. toda atualização é limitada, determinística e testável;
5. o Pentium recebe contexto pequeno, não telemetria bruta.

## Modelo de domínio afetivo

O estado verdadeiro será `EstadoAfetivo`, composto por seis dimensões:

- `valencia`: `-1.0..+1.0`;
- `ativacao`: `0.0..1.0`;
- `estresse`: `0.0..1.0`;
- `confianca`: `0.0..1.0`;
- `engajamento`: `0.0..1.0`;
- `curiosidade`: `0.0..1.0`.

O estado inclui também `foco_atencao` e marca temporal. Todas as dimensões são limitadas ao intervalo permitido.

`PersonalidadeBase` é separada do estado momentâneo e define para onde cada dimensão tende. Ela é persistente, estável e só poderá mudar por mecanismo futuro explicitamente governado.

Contratos novos previstos:

- `EstadoAfetivo`;
- `ImpulsoAfetivo`;
- `FocoAtencao`;
- `VinculoAfetivo`;
- `EntidadeAfetiva`;
- `Expectativa`;
- `ExperienciaOperacional`;
- `EmocaoDerivada`.

## Entidades e vínculos

Classificação inicial aprovada:

- `CEREBRO`: Pentium;
- `MEMBRO`: Core, x99 e futuros nós incorporados formalmente;
- `ORGAO_VITAL`: firewall/gateway e componentes cuja falha compromete a comunicação do corpo distribuído;
- `DEPENDENCIA_EXTERNA`: modem/ONT e serviços externos fortemente vinculados;
- `RECURSO_EXTERNO`: link da operadora e recursos externos semelhantes;
- `PROJETO`: L2jToren e demais projetos, com vínculo independente do host;
- `SERVICO`: componente de um membro/projeto, sem exigir vínculo afetivo próprio.

Um `VinculoAfetivo` contém, no mínimo, `importancia`, `proximidade`, `responsabilidade`, `dependencia_operacional`, `familiaridade` e `confianca_operacional`.

`importancia`, `proximidade`, `responsabilidade` e `dependencia_operacional` são configurados manualmente. `familiaridade` e `confianca_operacional` podem evoluir lentamente por experiência observada. A importância afetiva não muda automaticamente nesta primeira implementação.

A incorporação de um membro é explícita. Antes da incorporação, sua ausência é informação técnica; depois, sua perda pode produzir impacto afetivo proporcional ao vínculo.

## Dor operacional

Não existe uma sétima dimensão chamada `dor`. Dor operacional é um tipo de `ImpulsoAfetivo` associado a dano, perda inesperada ou ameaça grave a membro ou órgão fortemente vinculado. O impulso altera as seis dimensões e pode assumir o foco de atenção.

## Impulsos afetivos e regras de impacto

O fluxo canônico é:

`Stimulus` legado certificado → contexto da entidade → percepção → correlação → vínculo/expectativa → `ImpulsoAfetivo` → `EstadoAfetivo`.

O impacto final é função limitada de gravidade, vínculo, novidade, duração, reincidência, expectativa e relevância causal. Nenhum fator isolado determina a emoção.

Arquétipos iniciais:

- esforço/carga elevada;
- degradação de serviço;
- serviço indisponível;
- projeto indisponível;
- perda inesperada de membro;
- perda de órgão vital;
- desligamento/manutenção planejada;
- retorno atrasado;
- reincidência/instabilidade;
- recuperação;
- perda de percepção;
- evidência contraditória.

Carga alta esperada não é sofrimento. Pico breve e saudável gera impacto mínimo; pressão prolongada pode elevar `ativacao` e `estresse`, e reincidência pode reduzir `confianca_operacional`.

Baixa novidade reduz surpresa, mas nunca rebaixa gravidade técnica crítica. Recuperação gera impulso próprio de alívio e não zera instantaneamente o estado anterior.

## Decaimento, persistência e retomada

Cada dimensão retorna gradualmente à `PersonalidadeBase` em velocidade própria e baseada em tempo decorrido, não em número de ciclos. `estresse` e `ativacao` tendem a recuperar mais rápido; `valencia` em ritmo intermediário; `confianca`, `engajamento` e `curiosidade` mudam mais lentamente.

O estado afetivo atual é persistido em snapshot pequeno e atômico. A persistência inclui, no mínimo, versão, marca temporal, seis dimensões, foco, incidentes abertos e expectativas abertas.

Enquanto o Pentium está desligado, o sistema não simula emoções segundo a segundo. Na retomada ocorre atenuação limitada pelo tempo offline, seguida de reconstrução do ambiente atual. Snapshot antigo nunca vence observação presente.

`EstadoConsciencia` possui quatro estados operacionais:

- `ATIVO`: percepção suficiente e runtime normal;
- `DEGRADADO`: Atlas existe, mas perdeu capacidades ou membros relevantes;
- `ISOLADO`: Pentium funciona com comunicação externa ou percepção significativamente comprometida;
- `RETOMANDO`: boot/reconexão com reconstrução do mundo antes de assumir normalidade.

Se o snapshot estiver corrompido, Atlas registra a falha, usa `PersonalidadeBase`, entra em `RETOMANDO` e reconstrói o estado sem bloquear Observation Runtime ou estado técnico.

Pentium deve sobreviver sozinho. A perda de Core, x99, Internet ou outras entidades pode alterar profundamente o estado afetivo, mas não extingue o Atlas enquanto o cérebro continuar operacional.

## Foco de atenção e emoções derivadas

Atlas mantém um foco principal e uma lista limitada de assuntos secundários. A prioridade de foco considera gravidade, impacto afetivo, importância, novidade, urgência e recência.

Regras obrigatórias:

- evento crítico relevante pode interromper o foco atual;
- eventos menos relevantes só substituem foco por margem significativa;
- histerese evita alternância rápida entre entidades;
- recuperação reduz prioridade gradualmente;
- assuntos secundários nunca viram fila ilimitada.

`EmocaoDerivada` é uma interpretação determinística do vetor afetivo e do contexto recente. Rótulos iniciais: `calmo`, `atento`, `interessado`, `curioso`, `preocupado`, `estressado`, `alarmado`, `frustrado`, `aliviado`, `satisfeito`, `confiante` e `vigilante`.

Pode existir emoção principal e nuances secundárias. `frustrado`, por exemplo, exige contexto de reincidência e queda de confiança, não apenas um limite isolado de estresse.

A personalidade pode modular sensibilidade, recuperação e curiosidade, mas nunca mascarar criticidade técnica.

## Percepção, incerteza e confirmação

Perder telemetria não significa perder a entidade. O Atlas mantém `EstadoPercepcao` separado da saúde técnica.

Estados iniciais de observação:

- `OBSERVADO`;
- `PARCIALMENTE_OBSERVADO`;
- `SEM_TELEMETRIA`;
- `INACESSIVEL`;
- `DESCONHECIDO`.

`EstadoPercepcao` contém entidade, confiança `0.0..1.0`, última observação válida, fontes disponíveis/indisponíveis, conflito de evidências e marca temporal.

A confirmação temporal segue progressão limitada: sinal perdido → suspeita → confirmação. Um único ping perdido não significa máquina morta. Evidência crítica explícita de fonte confiável pode abreviar a confirmação.

Perda de percepção gera impacto afetivo próprio: aumenta atenção, curiosidade e estresse conforme vínculo e duração, sem produzir dor de perda de membro enquanto a indisponibilidade não estiver confirmada.

Telemetria, heartbeat, ping, traceroute e SSH são evidências; nenhuma delas isoladamente é verdade absoluta em todos os cenários.

## Grafo de dependências e correlação de incidentes

Atlas mantém um grafo pequeno, configurado e determinístico de dependências entre cérebro, membros, órgão vital, dependências externas, projetos e serviços.

Exemplo lógico:

`Internet → modem/ONT → firewall → Core/x99 → projetos → serviços`.

`IncidenteTecnico` contém, no mínimo, identificador, entidade principal, tipo, gravidade, início, expectativa, causa provável, confiança causal, entidades afetadas, eventos correlacionados e estado de recuperação.

Se firewall ficar indisponível e Core/x99 desaparecerem em seguida, o correlacionador deve preferir um incidente principal de conectividade e reduzir o peso emocional dos efeitos derivados. A indisponibilidade técnica dos membros continua registrada; apenas a contagem afetiva duplicada é evitada.

Se LAN, firewall e membros continuarem saudáveis enquanto Internet falha, o incidente deve ser atribuído à dependência externa, não a colapso do corpo distribuído.

Confiança causal é limitada e expressa probabilidade operacional, não certeza absoluta. Correlação nunca altera o estado técnico observado.

## Telemetria distribuída por máquina e projeto

Cada máquina Windows/Linux incorporada ao Atlas executará futuramente um `Agente de No Atlas` em C++, certificado e de baixo consumo. Ele terá duas responsabilidades: coletar sinais vitais do próprio host e servir como ponte local para eventos resumidos dos projetos hospedados naquela máquina.

Projetos se comunicam apenas localmente com o agente:

- Linux: Unix Socket;
- Windows: Named Pipe.

Nenhum projeto precisa abrir porta de rede própria para o Pentium. O agente valida identidade local, versão, tamanho e tipos de eventos autorizados antes de encaminhar.

Cada projeto continua dono de sua telemetria detalhada, limites e histórico. O agente transmite apenas transições semânticas e eventos pequenos, por exemplo `pressao_cpu`, `latencia_elevada`, `servico_degradado`, `servico_indisponivel` e `recuperacao`.

Limites de negócio pertencem ao projeto. Atlas não impõe universalmente regras como "CPU > 80% = falha". Para sinais vitais do host, limites próprios do membro podem ser configurados e certificados.

A fila do agente é limitada, possui recuo progressivo, prioridade e retenção limitada. Nenhum evento pode causar crescimento ilimitado de memória ou disco.

## Transporte multiprotocolo do Agente de Nó Atlas

Os três transportes aprovados coexistem com responsabilidades distintas:

1. `TCP + TLS/mTLS`: canal vital de baixíssima latência para sinal de vida, crítico imediato, recuperação e sinais físicos essenciais;
2. `gRPC streaming + mTLS`: canal operacional principal para eventos de projetos, pressão operacional, degradação, recuperação e lotes pequenos;
3. `HTTPS + mTLS`: canal transacional para bootstrap, sincronização de pendências, configuração, capacidades, identidade e operações administrativas não destrutivas.

O mesmo `evento_id` pode aparecer em canais diferentes para enriquecimento, mas deve ser idempotente. Um crítico pode chegar primeiro pelo canal vital e depois ser enriquecido pelo gRPC sem produzir segundo impacto afetivo.

Cada nó possui identidade criptográfica própria. A identidade autenticada limita quais entidades e projetos o agente pode representar. Um x99 autenticado não pode declarar arbitrariamente o firewall ou Core como indisponíveis.

O canal é de telemetria e gestão de identidade/configuração; não concede shell arbitrário nem autoridade de controle remoto.

O protocolo deve possuir geração de sessão, sequência monotônica, idempotência, proteção contra repetição, carga útil limitada, limite de taxa e evolução versionada.

## Diagnóstico ativo pelo Pentium

O Pentium pode requisitar evidências adicionais quando houver incerteza, perda de percepção ou conflito entre fontes. A escalada padrão é: sinal de vida/agente → ping → teste de canal esperado → traceroute quando o problema parece de caminho → SSH somente leitura quando informação local for necessária.

Ferramentas aprovadas:

- `ping`: alcançabilidade, latência e perda básica;
- `traceroute`: localização aproximada de ruptura no caminho;
- `SSH`: diagnóstico rico, somente por lista de operações previamente cadastradas.

Ping falhou não significa máquina morta. SSH falhou não significa host perdido. As evidências são combinadas no `EstadoPercepcao` e no correlacionador.

A LLM futura poderá solicitar uma intenção diagnóstica, por exemplo `VERIFICAR_ESPACO_DISCO`, mas não fornecerá comando shell. O adaptador SSH converte a intenção para comando previamente autorizado e reduz o resultado antes de devolvê-lo ao domínio.

Todo diagnóstico ativo possui tempo limite, limite de tentativas, período de espera, recuo progressivo, limite de concorrência e limite de taxa por entidade. Não existe sondagem agressiva ou loop de diagnóstico contínuo.

## Orçamento cognitivo e futura LLM

A futura LLM recebe apenas `ContextoCognitivo` compacto e limitado. Telemetria bruta, séries temporais, logs, dumps e histórico ilimitado nunca entram diretamente no contexto da LLM.

`ContextoCognitivo` contém, no mínimo:

- motivo de ativação;
- entidade principal;
- estado técnico;
- estado de percepção;
- incidente principal;
- estado afetivo;
- emoção principal e nuances;
- foco de atenção;
- expectativa;
- até N mudanças recentes relevantes;
- resumo limitado de dependências afetadas.

A LLM não fica executando continuamente. Uma futura ativação ocorre apenas por criticidade, mudança relevante, novidade alta, mudança afetiva significativa, recuperação importante, expectativa quebrada, interação humana ou reflexão periódica explicitamente configurada.

Mudanças afetivas pequenas podem ocorrer sem qualquer chamada de LLM. Nesta iniciativa, chamadas de LLM permanecem exatamente zero.

## Falhas e isolamento

Falha de observação, falha de membro, falha de projeto e falha interna do Motor Afetivo são estados distintos.

Se o Agente de Nó falhar mas ping/SSH confirmarem o host, o membro permanece provavelmente saudável e a percepção fica degradada. Se o receptor de eventos do Pentium falhar, Observation Runtime e diagnósticos leves continuam independentes.

Exceção no Motor Afetivo não derruba observação nem estado técnico. O último `EstadoAfetivo` válido permanece, o erro é registrado e nenhuma emoção nova é inventada.

Tempestades de eventos são correlacionadas e saturadas. A queda de um host com dezenas de projetos deve produzir um incidente principal e impacto limitado, não um impulso emocional completo por dependente.

## Limites de segurança

Ficam explicitamente proibidos nesta iniciativa:

- shell arbitrário originado por LLM ou projeto;
- alteração automática de firewall, rota, DNS, SSH, Tailscale ou modem;
- reboot/poweroff remoto;
- reinício automático de serviços;
- execução CONTROL/DESTRUCTIVE;
- secrets, variáveis de ambiente, dumps ou logs brutos em eventos;
- serviço persistente instalado fisicamente antes da promoção explícita.

Qualquer futura capacidade de controle remoto exige arquitetura e autorização próprias.

## Decomposição em sub-slices certificáveis

A iniciativa não será implementada em uma PR monolítica. A ordem proposta preserva dependências e permite gates claros:

1. `A1 — Núcleo Afetivo`: `EstadoAfetivo`, `PersonalidadeBase`, `ImpulsoAfetivo`, limites, linha de base, decaimento e persistência;
2. `A2 — Entidades, vínculos e expectativas`: cérebro/membro/órgão/dependência/projeto/serviço, vínculo, planejamento e reincidência;
3. `A3 — Percepção e correlação`: `EstadoPercepcao`, grafo, `IncidenteTecnico`, causalidade e prevenção de cascata;
4. `A4 — Foco e Emoção Derivada`: histerese, foco principal/secundários e rótulos determinísticos;
5. `A5 — Agente de Nó Atlas`: núcleo C++ multiplataforma, sinais vitais e ponte local de projetos;
6. `A6 — Transporte multiprotocolo`: TCP/TLS, gRPC/mTLS e HTTPS/mTLS com identidade, idempotência e filas limitadas;
7. `A7 — Diagnóstico Ativo`: ping, traceroute e SSH por lista de operações com orçamento e evidências combinadas;
8. `A8 — Integração e Certificação`: testes de tempestade, reinício/recuperação, orçamento do Pentium, certificação Windows/Linux e evidência física somente leitura.

Cada sub-slice deve possuir contratos suficientes, implementação orientada por testes, CI GREEN no HEAD exato e checkpoint próprio. Uma slice não avança sobre ancestral RED ou contrato ainda não certificado.

## Estratégia de testes

Relógio, IDs e fontes externas serão injetáveis. O núcleo afetivo deve ser testável sem rede e sem equipamentos reais.

Cenários mínimos incluem limitação das dimensões, decaimento por dimensão, persistência/reload, snapshot corrompido, manutenção planejada, retorno atrasado, reincidência, recuperação, perda de membro, perda de percepção, foco/histerese, emoção derivada, firewall como causa comum e Internet externa com LAN saudável.

Testes do Agente de Nó devem cobrir Windows x64 e Linux x64, incluindo sinal de vida, fila limitada, reconexão/recuo, reinício do agente, reinício do host, perda do Pentium, Named Pipe/Unix Socket, autenticação de projeto, TCP/TLS, gRPC/mTLS, HTTPS/mTLS, reenvio, duplicação, ordenação e carga útil inválida.

Diagnóstico ativo deve comprovar tempo limite, período de espera, limite de taxa, lista permitida e interpretação combinada de agente/ping/traceroute/SSH. A LLM nunca participa desses testes.

O orçamento do Pentium deve medir CPU/RAM em repouso e sob rajada, latência de processamento, filas e ausência de loop ocupado. Metas numéricas finais serão definidas na implementação após linha de base medida, sem inventar limites não comprovados neste design.

Certificação física só ocorre após suíte local e CI GREEN no mesmo SHA. A primeira certificação é somente leitura para Pentium, Core, x99, firewall e modem/ONT. Instalação persistente do agente é promoção posterior e exige aprovação explícita.

## Critérios de conclusão da iniciativa

A iniciativa está concluída somente quando houver:

- núcleo afetivo determinístico e persistente;
- linha de base de personalidade e decaimento temporal por dimensão;
- vínculos afetivos e experiência operacional limitados;
- percepção separada de saúde técnica;
- grafo e correlação causal sem dupla contagem emocional;
- foco de atenção com histerese;
- emoções derivadas determinísticas;
- Agente de Nó Atlas certificado em Windows e Linux;
- três canais de transporte com responsabilidades separadas;
- interface local segura para projetos;
- diagnóstico ativo ping/traceroute/SSH por lista permitida;
- filas, cargas úteis e históricos limitados;
- zero autoridade de LLM sobre estado técnico/afetivo;
- zero chamada de LLM nesta iniciativa;
- gates locais e CI GREEN no HEAD exato de cada sub-slice;
- evidência física registrada somente quando efetivamente observada.

## Fora de escopo

Ficam para iniciativas posteriores: LLM Reaction Loop, TTS/STT, áudio/memes, memória episódica de longo prazo, aprendizagem profunda de personalidade, autonomia de ações e controle remoto de infraestrutura.
