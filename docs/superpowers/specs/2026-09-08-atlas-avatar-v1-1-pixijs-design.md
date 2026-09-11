# Atlas Avatar v1.1 — PixiJS Full-Body Design

## Objetivo

Evoluir o Avatar v1 do Atlas para um renderer 2D full-body em PixiJS, preservando o contrato `EstadoVisualAtlas`, o dashboard LAN estritamente read-only e o isolamento entre observação, cognição, afeto e apresentação.

Esta especificação complementa `docs/implementation/2026-09-04-atlas-avatar-v1-design.md`. Todos os requisitos da v1 continuam válidos, exceto a escolha do renderer primário.

## Renderer v1.1

- renderer primário: `pixijs_full_body`;
- versão fixada: `pixi.js@8.20.1`;
- runtime: bundle local no Pentium, sem dependência de CDN após instalação;
- origem de instalação: asset oficial do release GitHub v8.20.1;
- integridade obrigatória: SHA-256 `9948591083793305468d73915a3ea85032dcf8e32eee7a1328585050d7a14d53`;
- fallback: SVG por camadas já existente no dashboard;
- falha do renderer não afeta Atlas Core, Observation Runtime, voz ou estado afetivo.

O PixiJS v8 usa inicialização assíncrona de `Application`. A aplicação visual deve falhar de forma isolada: bundle ausente, falha de WebGL/WebGPU/Canvas ou erro de inicialização mantém o SVG disponível.

## Fronteiras

`EstadoVisualAtlas` permanece a única entrada semântica do avatar. O renderer não consulta Motor Afetivo, Observation Runtime, LLM, áudio bruto, telemetria técnica ou endpoints de controle.

## Comportamento visual mínimo

O rig PixiJS deve possuir corpo, cabelo, cabeça, olhos, sobrancelhas, boca e dois braços. Deve representar os quatro modos e os sete arquétipos da v1, além de direção do olhar, gesto, fala, escuta, dúvida de identidade, idle limitado, blink e redução de movimento.

## Normalização

Antes do renderer, a camada de apresentação deve:

- limitar intensidades e velocidades a `0.0..1.0`;
- limitar `transicao_ms` a `120..1500`;
- usar `OCIOSO` e `SERENO` para valores desconhecidos;
- usar foco neutro e olhar central quando ausentes;
- nunca reclassificar estado técnico ou afetivo.

## Operação

O dashboard continua GET-only. Assets JavaScript estáticos podem ter até 1 MiB; respostas dinâmicas permanecem limitadas a 256 KiB. O bundle PixiJS é baixado apenas durante instalação, validado por SHA-256 e servido localmente pelo dashboard.
