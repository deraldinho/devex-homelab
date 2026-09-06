# PRD-0006 — Atlas Local Intelligence

## Contexto

O `pentium` é o `homelab.control` do DevEx HomeLab e já possui contratos de heartbeat e Agent empilhados na PR #19. A Issue #20 adiciona uma camada local de interação que representa o estado do homelab inteiro — MikroTik, Pentium, Core, x99, Internet/DNS, serviços, jobs e runners — sem transformar a LLM em autoridade operacional.

## Objetivo

Permitir que o Atlas observe o estado global do homelab, expresse esse estado por uma linguagem sonora variada e, por fases, receba comandos de voz, explique eventos e acione operações allowlisted.

## Requisitos funcionais

### RF1 — Estado global

Produzir `global_state`, `intensity` e `reasons` a partir de observed state versionado.

### RF2 — Reações variadas

Cada estado/emoção deve mapear para um pool de reações, com pesos, anti-repeat, raridade e cooldown.

### RF3 — Memes opcionais

Memes podem ser escolhidos como reação emocional contextual, mas não podem ser o único sinal de evento crítico.

### RF4 — Journal

Registrar transições relevantes em JSONL com timestamp, estado anterior/novo, intensidade, razões e reação escolhida.

### RF5 — Voz local

Em fase posterior, reconhecer wake word/comando, converter para intent e responder localmente. A primeira versão de voz deve ser READ-only.

### RF6 — Mini LLM limitada

A mini LLM deve interpretar/sumarizar, mas não executar shell. O candidato inicial é Qwen3-0.6B Q4 via llama.cpp, condicionado a benchmark físico.

### RF7 — Ações seguras

- `READ`: automáticas quando allowlisted;
- `CONTROL`: apenas ações nominais explicitamente allowlisted;
- `DESTRUCTIVE`: confirmação humana obrigatória.

### RF8 — Fronteira semântica interna

Traduzir contratos observados para `EventoSemantico` exclusivamente dentro do Atlas. Nenhum serviço externo precisa conhecer o vocabulário semântico interno do Atlas, seus códigos compactos ou o registry.

### RF9 - Fast Router deterministico

Classificar `EventoSemantico` por score bounded em lanes internas. Criticidade e recuperação não aguardam LLM; baixa novidade prefere cache; apenas ambiguidade nova pode receber `SLOW_LLM`, sempre fora do caminho crítico.

## Requisitos não funcionais

- funcionamento de Health/Reaction sem Internet;
- consumo compatível com ~2,5 GiB de RAM no Pentium;
- sem polling agressivo;
- saída e logs ASCII/UTF-8 portáveis;
- nenhum secret ou mídia sem licença versionado;
- testes determinísticos para seleção de reação;
- nenhuma dependência de x99 para operação diária;
- nenhuma dependência de serviços externos no registry ou nos códigos semânticos internos do Atlas;
- percepção, emoção e reação imediata não dependem de resposta da LLM.

## S1 — Semantic Event + Adapter Boundary

Escopo: modelo `EventoSemantico` bounded/versionado, `RegistroSemantico` interno, adapters explícitos para Pentium/Core/x99/Wi-Fi e `FronteiraSemantica` com fan-out máximo de 32. A S1 não altera contratos dos serviços observados e prepara a S2 Fast Router.

Definition of Done S1: source desconhecida falha fechada; payload composto não atravessa `attributes`; códigos compactos são internos; installer/CI empacotam a slice; suíte Atlas GREEN no HEAD exato.

## S2 - Fast Router

Escopo: score de pré-julgamento determinístico e lanes `DROP`, `FAST_REACTION`, `AFFECT`, `CACHE_LOOKUP` e `SLOW_LLM`, sem executar nenhuma delas.

## Primeira slice — Atlas State & Reaction Foundation

Escopo:

- tipos canônicos de estado/intensidade/evento;
- agregação de sinais já classificados;
- transição `recovered`;
- Reaction Engine determinístico/testável;
- configuração de pools sem mídia obrigatória;
- journal JSONL;
- CLI para validar snapshots e produzir uma decisão de reação;
- CI com py_compile, JSON validation e unittest.

Não escopo:

- download ou curadoria de memes;
- reprodução real no host;
- Qwen/llama.cpp;
- microfone/STT/TTS;
- mudanças no MikroTik, Tailscale, SSH ou firewall;
- auto-remediação.

## Definition of Done da primeira slice

- TDD RED antecede implementação;
- estados e intensidade possuem contrato estável;
- agregador nunca executa probes concorrentes aos contratos existentes;
- `critical` de componente obrigatório prevalece sobre estados menores;
- recuperação gera evento `recovered` antes de retornar a `healthy`;
- Reaction Engine evita repetição recente e respeita cooldown;
- meme nunca suprime alerta crítico canônico;
- journal é append-only e parseável linha a linha;
- CI GREEN no HEAD exato;
- deploy físico só após reconciliação com o Pentium e aprovação;
- checkpoint registra SHA, CI, evidência física e próximo passo.
