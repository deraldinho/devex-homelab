# Atlas C4 — Policy/Capabilities

## Objetivo

Fechar a fronteira de autoridade entre a saída da LLM e qualquer ação futura do Atlas.

## Implementação

- catálogo fechado `CapabilityRegistry`;
- níveis `READ`, `CONTROL`, `DESTRUCTIVE`;
- parâmetros tipados e exatos;
- `PolicyCapabilities` fail-closed;
- `READ` automático somente em allowlist explícita;
- `CONTROL` somente em policy explícita;
- `DESTRUCTIVE` exige confirmação humana independente;
- parser JSON/schema bounded da resposta LLM;
- saída inválida vira fallback e nunca intenção executável;
- Reaction Loop expõe decisão, mas não executa capability.

## Gates

- TDD RED→GREEN;
- regressão completa Atlas;
- `bash -n` no instalador;
- `git diff --check` contra C3;
- Foundation CI no HEAD exato antes de promoção.
