# Atlas S1 — Semantic Event + Adapter Boundary

## Objetivo

Criar a fronteira semântica interna do Atlas sem exigir que Core, x99, Pentium, L2jToren ou qualquer serviço externo conheça o vocabulário cognitivo do Atlas.

O contrato externo permanece pertencendo ao domínio que o publica. A tradução para significado canônico acontece exclusivamente dentro do Atlas, depois que os adapters de observação já produziram um `Stimulus` normalizado.

## Princípio arquitetural

> Nenhum serviço externo depende do vocabulário, códigos ou registry semântico interno do Atlas.

Fluxo canônico:

```text
contrato externo -> StimulusSource -> Stimulus -> FronteiraSemantica
                                              -> EventoSemantico
                                              -> futuras S2/S3/S4
```

A S1 não altera o contrato dos serviços observados, não adiciona endpoint e não exige deploy neles.

## Modelo semântico

`EventoSemantico` é imutável, bounded e versionado. Código Python trabalha com enums legíveis; códigos numéricos existem somente para serialização compacta, fingerprint/cache e futuro contrato reduzido com a LLM.
Campos mínimos:

- `schema_version=1`;
- `entity`: entidade canônica conhecida pelo Atlas;
- `event`: tipo de evento semântico;
- `state`: estado semântico reduzido;
- `severity`: severidade técnica herdada/normalizada;
- `novelty`: `0.0..1.0` quantizada somente na serialização compacta;
- `correlation_id`: correlação preservada do Stimulus;
- `attributes`: mapa pequeno de escalares permitidos, máximo 16 entradas.

Não é permitido carregar texto livre, logs brutos, payloads arbitrários ou histórico dentro de `EventoSemantico`.

## Registry interno

Um `RegistroSemantico` versionado mantém os códigos compactos das entidades/eventos/estados conhecidos. O código normal nunca depende dos inteiros diretamente.

Exemplo conceitual:

```text
CORE -> entity code 2
STATE_CHANGED -> event code 2
DEGRADED -> state code 2
```

Trocar códigos ou schema exige nova versão. Serviços externos nunca importam este registry.

## Adapter boundary

Cada fonte conhecida possui tradução explícita. A fronteira seleciona adapter por `stimulus.source` e retorna `tuple[EventoSemantico, ...]`, permitindo fan-out bounded para fontes como presença Wi-Fi.
Fontes iniciais obrigatórias:

- `pentium.self` -> `PENTIUM`;
- `core` -> `CORE`;
- `x99` -> `X99`;
- `wifi.presence` -> `WIFI_ZONE` e eventos de presença bounded.

`source_error` é traduzido explicitamente para indisponibilidade da fonte. Fonte sem adapter gera erro de fronteira; não existe fallback que invente significado.

## Integração S1

A S1 entrega uma `FronteiraSemantica` utilizável pelos próximos consumidores e testes de integração sobre Stimulus reais. Ela não substitui ainda o pipeline de percepção existente e não coloca a LLM no caminho crítico.

A futura S2 consumirá `EventoSemantico` no Fast Router. A S1 deve portanto ser independente de LLM, cache vetorial, áudio e Action Engine.

## Bounds e falhas

- máximo 16 atributos escalares por evento;
- strings de atributo limitadas a 128 caracteres;
- fan-out máximo de 32 eventos por Stimulus;
- valores compostos/listas não entram em `attributes`;
- source desconhecida ou payload semanticamente inválido falha fechado;
- falha semântica não altera o estado técnico determinístico já observado.

## Definition of Done

- spec, arquitetura e PRD deixam explícito que o dicionário é interno;
- modelo semântico e registry possuem testes determinísticos;
- adapters traduzem Pentium/Core/x99/Wi-Fi sem alterar contratos externos;
- compact serialization/fingerprint é estável e sem prosa;
- unknown source e payload fora dos bounds são rejeitados;
- instalação e Foundation CI empacotam/validam S1;
- suíte Atlas completa GREEN no HEAD exato;
- PR permanece sem merge até decisão explícita do usuário;
- `/checkpoint` registra SHA, CI e próximo passo S2 Fast Router.
