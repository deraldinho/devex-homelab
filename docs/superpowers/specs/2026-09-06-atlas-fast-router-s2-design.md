# Atlas S2 — Fast Router

## Objetivo

Adicionar um roteador semântico determinístico e de custo constante entre `EventoSemantico` e os caminhos de reação do Atlas.

A S2 não executa reação, emoção, cache ou LLM. Ela somente produz uma decisão tipada e bounded.

## Fronteira

```text
EventoSemantico
      |
      v
   FastRouter
      |
      +--> DROP
      +--> FAST_REACTION
      +--> AFFECT
      +--> CACHE_LOOKUP
      `--> SLOW_LLM
```

Uma decisão pode conter múltiplas lanes, exceto `DROP`, que é exclusivo.
## Regras de negócio

1. Baseline saudável e informativo pode ser descartado sem LLM.
2. Evento crítico nunca é suprimido por cache: `FAST_REACTION + AFFECT`.
3. Recuperação relevante usa `FAST_REACTION + AFFECT`; não precisa de LLM para produzir alívio imediato.
4. Evento não crítico já conhecido, com baixa novidade, usa `AFFECT + CACHE_LOOKUP` e evita nova inferência.
5. Evento novo com score alto segue fast path determinístico, sem esperar LLM.
6. Apenas eventos novos em faixa ambígua podem receber `SLOW_LLM`, sempre junto ao caminho afetivo e de forma não bloqueante.
7. Eventos de presença Wi-Fi não acordam a LLM nesta slice; contexto de vínculo poderá elevar isso em slice posterior.
8. Nenhuma lane executa ações ou decide saúde/autorização.

## Score de pré-julgamento

O score `0..1` usa somente enums e novidade já existentes:

- severidade: info `0.10`, notice `0.30`, warning `0.65`, critical `1.00`;
- boost do tipo de evento bounded;
- novidade contribui no máximo `0.10`;
- resultado é clampado em `0..1`.
## Política versionada

A configuração define:

- `drop_score_max`;
- `cache_novelty_max`;
- `fast_reaction_score_min`;
- `slow_llm_score_min` e `slow_llm_score_max`;
- `slow_llm_novelty_min`.

Os limites devem ser coerentes e falham fechados se inválidos.

## Restrições

- sem imports de `llm_gateway`, `cognitive_cache`, áudio, shell, SSH ou rede;
- processamento puro em memória, sem I/O;
- ordem de lanes canônica para serialização/testes;
- config carregada na inicialização, nunca por evento;
- S2 não altera contratos externos nem `StimulusSource`.

## DoD

- TDD RED antes da implementação;
- score e roteamento determinísticos;
- critical e recovery comprovadamente independentes da LLM;
- baixa novidade comprovadamente evita inferência;
- evento ambíguo novo pode deferir para slow path;
- installer/CI empacotam S2;
- suíte completa GREEN e Foundation CI GREEN no HEAD exato;
- checkpoint na PR da S2.