# Atlas V1 Always-On Voice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tornar o Atlas comunicável no Pentium por texto e voz local, com wake phrase `Atlas`, STT local, TTS ao vivo e serviço residente.

**Architecture:** A V1 implementa apenas a trilha de voz já definida em `docs/architecture/atlas-local-intelligence-design.md`. `atlas-voice.service` owns captura/VAD/STT; `HumanInteractionGateway` adapta texto para `Stimulus human_interaction`; `ReactionLoopCognitivo` e `LLMGateway` continuam owners da cognição; `LiveTtsBackend` sintetiza fala dinâmica. Audio/Reaction Engine permanece separado para memes/MP3/efeitos.

**Tech Stack:** Python stdlib, ALSA, whisper.cpp, Piper TTS, llama.cpp/Qwen GGUF, systemd --user, unittest.

**Spec:** `docs/superpowers/specs/2026-09-06-atlas-v1-always-on-voice-design.md`

## Global Constraints
- Nenhum áudio bruto persistido por padrão.
- `Atlas` é prefixo obrigatório para interação por voz.
- Voz não concede autorização CONTROL.
- Nenhuma API pública aceita shell arbitrário.
- TTS linguístico é sintetizado ao vivo; MP3 permanece permitido no Audio/Reaction Engine.
- Buffers, tempo de utterance, saída, retries e filas são bounded.
- CI não auto-certifica microfone, alto-falante ou percepção humana.
