# Atlas Avatar v1.1 — PixiJS Full-Body Design

## Objetivo

Evoluir o Avatar v1 do Atlas para um renderer 2D full-body em PixiJS, preservando o contrato `EstadoVisualAtlas`, o dashboard LAN estritamente read-only e o isolamento entre observação, cognição, afeto e apresentação.

Esta especificação complementa `docs/implementation/2026-09-04-atlas-avatar-v1-design.md`. Todos os requisitos da v1 continuam válidos, exceto a escolha do renderer primário.

## Override de renderer

- renderer primário: `pixijs_full_body`;
- versão fixada: `pixi.js@8.20.1`;
- distribuição: bundle local vendorizado, sem CDN;
- fallback: SVG por camadas já existente no dashboard;
- renderer executa apenas no navegador;
- nenhuma dependência de GPU é obrigatória para o funcionamento do Atlas Core.

O PixiJS v8 usa inicialização assíncrona de `Application`. A aplicação visual deve falhar de forma isolada: ausência do bundle, falha de WebGL/WebGPU/Canvas ou erro de inicialização mantém o SVG disponível.

## Fronteiras

`EstadoVisualAtlas` permanece a única entrada semântica do avatar. O renderer não consulta Motor Afetivo, Observation Runtime, LLM, áudio bruto, telemetria técnica ou endpoints de controle.