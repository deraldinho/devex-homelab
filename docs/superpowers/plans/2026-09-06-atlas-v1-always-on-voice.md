# Atlas V1 Always-On Voice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Manter o Atlas residente no Pentium, ouvir fala local continuamente, aceitar somente segmentos iniciados por `Atlas`, processar a interação humana no pipeline cognitivo e responder por voz local sem conceder autoridade de CONTROL.

**Architecture:** Um `VoiceRuntime` bounded coordena captura ALSA, VAD/segmentação, STT local, wake phrase, gateway humano, cérebro cognitivo e TTS. STT/TTS/brain são adapters substituíveis; áudio bruto vive apenas em memória/temporário efêmero. O serviço `systemd --user` inicia no boot e degrada fechado quando hardware/modelos estão ausentes.

**Tech Stack:** Python 3.14 stdlib, ALSA (`arecord`/`aplay`), whisper.cpp, llama.cpp/Qwen3-0.6B, eSpeak NG, systemd --user, unittest.

**Spec:** `docs/superpowers/specs/2026-09-06-atlas-v1-always-on-voice-design.md`

## Global Constraints
- Branch isolada `atlas/issue-20-v1-always-on-voice`, baseada no I1 exato vigente.
- Nenhum PCM bruto persistente; temporários são apagados no mesmo ciclo.
- Wake phrase obrigatória `Atlas`; texto sem wake phrase não ativa LLM.
- `CONTROL` continua dependendo de capability policy, autorização e confirmação; voz não autoriza.
- Todo frame, segmento, subprocesso, stdout/stderr, fila e retry deve possuir bound explícito.
- CI nunca declara certificação física.

---
### Task 1: Human interaction + wake phrase

**Files:**
- Create: `infrastructure/pentium/atlas/human_interaction.py`
- Test: `infrastructure/pentium/atlas/tests/test_human_interaction.py`

**Interfaces:**
- Produces: `extract_atlas_utterance(text: str, max_chars: int) -> str | None`.
- Produces: `build_human_stimulus(text, source, timestamp) -> Stimulus`.

- [ ] RED: aceita `Atlas, como esta o x99?`, remove wake phrase e limita texto.
- [ ] RED: rejeita frase sem `Atlas`, vazia ou só wake phrase como comando técnico.
- [ ] RED: stimulus usa `kind=human_interaction`, `source=human.voice|human.cli` e payload bounded.
- [ ] GREEN: implementar somente normalização, bounds e criação do stimulus.
- [ ] Rodar teste isolado e regressão cognitiva; commit da task.

### Task 2: Voice adapters + bounded runtime

**Files:**
- Create: `infrastructure/pentium/atlas/voice_adapters.py`
- Create: `infrastructure/pentium/atlas/voice_runtime.py`
- Test: `infrastructure/pentium/atlas/tests/test_voice_runtime.py`

**Interfaces:**
- `AlsaCapture.read_frame() -> bytes`; `WhisperCppStt.transcribe(pcm: bytes) -> str`.
- `EspeakNgTts.speak(text: str) -> None`; `VoiceRuntime.run_once() -> VoiceCycleResult`.

- [ ] RED: silêncio não chama STT; fala bounded gera um único segmento.
- [ ] RED: transcrição sem wake não chama brain; com wake chama uma vez.
- [ ] RED: runtime entra `SPEAKING`, pausa captura, executa TTS e retorna `LISTENING`.
- [ ] RED: timeout/erro STT/TTS/brain vira `DEGRADED` sem loop infinito nem áudio persistido.
- [ ] GREEN: implementar VAD RMS stdlib, segmentador bounded e subprocess adapters `shell=False`.
- [ ] Rodar testes isolados e regressão Atlas; commit da task.

### Task 3: Cognitive bridge + CLI

**Files:**
- Create: `infrastructure/pentium/atlas/human_cognitive_bridge.py`
- Create: `infrastructure/pentium/atlas/chat_cli.py`
- Test: `infrastructure/pentium/atlas/tests/test_human_cognitive_bridge.py`
- Test: `infrastructure/pentium/atlas/tests/test_chat_cli.py`

**Interfaces:**
- `HumanCognitiveBridge.respond(text: str, source: str) -> str | None`.
- Reusa `ReactionLoopCognitivo.processar(...)`; injeta o stimulus humano em `mudancas_recentes` e `interacao_humana=True`.

- [ ] RED: interação humana passa pelo builder/policy/gateway e nunca chama Managed CONTROL diretamente.
- [ ] RED: resposta nula/degradada vira mensagem local segura; intenção que requer confirmação não executa.
- [ ] RED: CLI oferece `/status`, `/help`, `/exit` e texto normal pelo mesmo bridge.
- [ ] GREEN: implementar composition bridge mínimo e CLI sem duplicar policy.
- [ ] Rodar testes e regressão; commit da task.

### Task 4: Packaging + resident service

**Files:**
- Create: `infrastructure/pentium/atlas/config_voice.json`
- Create: `infrastructure/pentium/atlas/voice_service.py`
- Create: `infrastructure/pentium/systemd/atlas-voice.service`
- Modify: `infrastructure/pentium/atlas/install-user.sh`
- Modify: `.github/workflows/foundation-ci.yml`
- Test: `infrastructure/pentium/atlas/tests/test_v1_voice_packaging.py`

- [ ] RED: installer ainda não empacota V1, config nem unit.
- [ ] GREEN: empacotar módulos/config, py_compile/json, instalar unit em `~/.config/systemd/user`, `daemon-reload` e marker `ATLAS_V1_ALWAYS_ON_VOICE_INSTALL_PASS`.
- [ ] GREEN: CI executa testes V1 e marker `DEVEX_HOMELAB_ATLAS_V1_VOICE_RUNTIME_PASS` sem declarar hardware físico.
- [ ] Rodar shell/json/py_compile + suites completas; commit da task.

### Task 5: Physical provisioning + exact-SHA certification

**Files:**
- Create: `infrastructure/pentium/atlas/provision-voice-user.sh`
- Test: `infrastructure/pentium/atlas/tests/test_v1_voice_provisioning.py`

- [ ] RED/GREEN: script só opera em `$HOME`, fixa versões/checksums e não usa sudo.
- [ ] Provisionar CMake local se necessário, whisper.cpp + modelo multilingual tiny/base, llama.cpp + Qwen3-0.6B Q4 e eSpeak NG user-local.
- [ ] Gerar archive do HEAD exato, SHA256 local/remoto, instalar e reiniciar `atlas-voice.service`.
- [ ] Verificar ALSA capture real, wake phrase, STT pt-BR, brain/LLM, TTS audível, retorno a LISTENING e default-deny CONTROL.
- [ ] Rodar soak curto de RSS/restarts e revalidar `pentium-agent.service`, WiFi e x99 READ.
- [ ] Somente após evidência: push da branch, CI no HEAD exato e checkpoint/as-built.
