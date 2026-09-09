#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_ROOT="${HOME}/pentium-agent"
TARGET_DIR="${TARGET_ROOT}/atlas"

command -v hermes >/dev/null 2>&1 || { echo "Hermes CLI nao encontrado no PATH" >&2; exit 2; }

install -d -m 0755 "${TARGET_DIR}"

for file in \
  __init__.py \
  state_model.py \
  health_engine.py \
  reaction_engine.py \
  journal.py \
  stimulus_model.py \
  modelo_evento_semantico.py \
  registro_semantico.py \
  adaptadores_semanticos.py \
  modelo_fast_router.py \
  configuracao_fast_router.py \
  fast_router.py \
  modelo_fast_dispatch.py \
  fast_dispatch.py \
  slow_llm_defer_queue.py \
  stimulus_bus.py \
  stimulus_journal.py \
  network_discovery.py \
  network_discovery_smoke.py \
  presence_registry.py \
  presence_persistence.py \
  stimulus_sources.py \
  observation_runtime.py \
  dual_zone_runtime.py \
  i1_certification.py \
  modelo_afetivo.py \
  configuracao_afetiva.py \
  decaimento_afetivo.py \
  motor_afetivo.py \
  persistencia_afetiva.py \
  modelo_contexto_afetivo.py \
  contexto_afetivo.py \
  persistencia_contexto_afetivo.py \
  modelo_percepcao.py \
  percepcao.py \
  adaptador_stimulus_percepcao.py \
  grafo_dependencias.py \
  modelo_incidente.py \
  correlacionador_incidentes.py \
  pipeline_percepcao_correlacao.py \
  persistencia_percepcao_correlacao.py \
  modelo_foco.py \
  motor_foco.py \
  emocao_derivada.py \
  contexto_foco_emocao.py \
  persistencia_foco_emocao.py \
  modelo_visual_atlas.py \
  compositor_visual_afetivo.py \
  visual_state_publisher.py \
  affective_runtime.py \
  adaptador_impacto_afetivo.py \
  pipeline_afetivo_observacional.py \
  affective_composition.py \
  affective_interaction_ipc.py \
  observation_daemon.py \
  affective_boot_certification.py \
  cognitive_observation_projection.py \
  cognitive_context_bridge_certification.py \
  cognitive_daemon.py \
  cognitive_observability.py \
  action_plan.py \
  action_plan_store.py \
  action_planner.py \
  action_policy.py \
  action_executors.py \
  chat_inbox.py \
  modelo_contexto_cognitivo.py \
  configuracao_cognitiva.py \
  contexto_cognitivo.py \
  politica_ativacao_cognitiva.py \
  modelo_llm_gateway.py \
  config_hermes.py \
  hermes_preflight.py \
  hermes_physical_smoke.py \
  hermes_adapter.py \
  llm_gateway.py \
  prompt_cognitivo.py \
  reaction_loop_cognitivo.py \
  reasoning_policy.py \
  capability_registry.py \
  policy_capabilities.py \
  saida_cognitiva.py \
  certificacao_cognitiva.py \
  sampler_linux_cognitivo.py \
  fontes_fisicas_cognitivas.py \
  c5_physical_runner.py \
  c5_physical_orchestrator.py \
  c5_physical_evaluator.py \
  c5_physical_campaign.py \
  c5_observation_probe.py \
  memory_model.py \
  memory_store.py \
  memory_manager.py \
  memory_retriever.py \
  config_memory.py \
  cognitive_cache.py \
  config_cache.py \
  unix_http.py \
  voice_gate.py \
  live_tts.py \
  alsa_capture.py \
  alsa_stream.py \
  adaptive_noise_canceller.py \
  utterance_capture.py \
  streaming_vad.py \
  whisper_stt.py \
  voice_runtime.py \
  chat_cli.py \
  energy_vad.py \
  adaptive_vad.py \
  transcript_filter.py \
  human_interaction.py \
  human_context.py \
  voice_daemon.py \
  cli.py; do
  install -m 0644 "${SOURCE_DIR}/${file}" "${TARGET_DIR}/${file}"
done

for config in config.json observation_config.json config_afetiva.json config_percepcao.json config_foco_emocao.json config_affective_runtime.json config_observation_affective.json config_cognitiva.json config_hermes.json config_memory.json config_cache.json config_fast_router.json config_voice.json; do
  install -m 0644 "${SOURCE_DIR}/${config}" "${TARGET_DIR}/${config}"
done

install -m 0755 "${SOURCE_DIR}/prepare-hermes-atlas.sh" "${TARGET_DIR}/prepare-hermes-atlas.sh"

python3 -m py_compile \
  "${TARGET_DIR}/state_model.py" \
  "${TARGET_DIR}/health_engine.py" \
  "${TARGET_DIR}/reaction_engine.py" \
  "${TARGET_DIR}/journal.py" \
  "${TARGET_DIR}/stimulus_model.py" \
  "${TARGET_DIR}/modelo_evento_semantico.py" \
  "${TARGET_DIR}/registro_semantico.py" \
  "${TARGET_DIR}/adaptadores_semanticos.py" \
  "${TARGET_DIR}/modelo_fast_router.py" \
  "${TARGET_DIR}/configuracao_fast_router.py" \
  "${TARGET_DIR}/fast_router.py" \
  "${TARGET_DIR}/modelo_fast_dispatch.py" \
  "${TARGET_DIR}/fast_dispatch.py" \
  "${TARGET_DIR}/slow_llm_defer_queue.py" \
  "${TARGET_DIR}/stimulus_bus.py" \
  "${TARGET_DIR}/stimulus_journal.py" \
  "${TARGET_DIR}/network_discovery.py" \
  "${TARGET_DIR}/network_discovery_smoke.py" \
  "${TARGET_DIR}/presence_registry.py" \
  "${TARGET_DIR}/presence_persistence.py" \
  "${TARGET_DIR}/stimulus_sources.py" \
  "${TARGET_DIR}/observation_runtime.py" \
  "${TARGET_DIR}/dual_zone_runtime.py" \
  "${TARGET_DIR}/i1_certification.py" \
  "${TARGET_DIR}/modelo_afetivo.py" \
  "${TARGET_DIR}/configuracao_afetiva.py" \
  "${TARGET_DIR}/decaimento_afetivo.py" \
  "${TARGET_DIR}/motor_afetivo.py" \
  "${TARGET_DIR}/persistencia_afetiva.py" \
  "${TARGET_DIR}/modelo_contexto_afetivo.py" \
  "${TARGET_DIR}/contexto_afetivo.py" \
  "${TARGET_DIR}/persistencia_contexto_afetivo.py" \
  "${TARGET_DIR}/modelo_percepcao.py" \
  "${TARGET_DIR}/percepcao.py" \
  "${TARGET_DIR}/adaptador_stimulus_percepcao.py" \
  "${TARGET_DIR}/grafo_dependencias.py" \
  "${TARGET_DIR}/modelo_incidente.py" \
  "${TARGET_DIR}/correlacionador_incidentes.py" \
  "${TARGET_DIR}/pipeline_percepcao_correlacao.py" \
  "${TARGET_DIR}/persistencia_percepcao_correlacao.py" \
  "${TARGET_DIR}/modelo_foco.py" \
  "${TARGET_DIR}/motor_foco.py" \
  "${TARGET_DIR}/emocao_derivada.py" \
  "${TARGET_DIR}/contexto_foco_emocao.py" \
  "${TARGET_DIR}/persistencia_foco_emocao.py" \
  "${TARGET_DIR}/modelo_visual_atlas.py" \
  "${TARGET_DIR}/compositor_visual_afetivo.py" \
  "${TARGET_DIR}/visual_state_publisher.py" \
  "${TARGET_DIR}/affective_runtime.py" \
  "${TARGET_DIR}/adaptador_impacto_afetivo.py" \
  "${TARGET_DIR}/pipeline_afetivo_observacional.py" \
  "${TARGET_DIR}/affective_composition.py" \
  "${TARGET_DIR}/affective_interaction_ipc.py" \
  "${TARGET_DIR}/observation_daemon.py" \
  "${TARGET_DIR}/affective_boot_certification.py" \
  "${TARGET_DIR}/cognitive_observation_projection.py" \
  "${TARGET_DIR}/cognitive_context_bridge_certification.py" \
  "${TARGET_DIR}/cognitive_daemon.py" \
  "${TARGET_DIR}/cognitive_observability.py" \
  "${TARGET_DIR}/action_plan.py" \
  "${TARGET_DIR}/action_plan_store.py" \
  "${TARGET_DIR}/action_planner.py" \
  "${TARGET_DIR}/action_policy.py" \
  "${TARGET_DIR}/action_executors.py" \
  "${TARGET_DIR}/chat_inbox.py" \
  "${TARGET_DIR}/modelo_contexto_cognitivo.py" \
  "${TARGET_DIR}/configuracao_cognitiva.py" \
  "${TARGET_DIR}/contexto_cognitivo.py" \
  "${TARGET_DIR}/politica_ativacao_cognitiva.py" \
  "${TARGET_DIR}/modelo_llm_gateway.py" \
  "${TARGET_DIR}/config_hermes.py" \
  "${TARGET_DIR}/hermes_preflight.py" \
  "${TARGET_DIR}/hermes_physical_smoke.py" \
  "${TARGET_DIR}/hermes_adapter.py" \
  "${TARGET_DIR}/llm_gateway.py" \
  "${TARGET_DIR}/prompt_cognitivo.py" \
  "${TARGET_DIR}/reaction_loop_cognitivo.py" \
  "${TARGET_DIR}/reasoning_policy.py" \
  "${TARGET_DIR}/capability_registry.py" \
  "${TARGET_DIR}/policy_capabilities.py" \
  "${TARGET_DIR}/saida_cognitiva.py" \
  "${TARGET_DIR}/certificacao_cognitiva.py" \
  "${TARGET_DIR}/sampler_linux_cognitivo.py" \
  "${TARGET_DIR}/fontes_fisicas_cognitivas.py" \
  "${TARGET_DIR}/c5_physical_runner.py" \
  "${TARGET_DIR}/c5_physical_orchestrator.py" \
  "${TARGET_DIR}/c5_physical_evaluator.py" \
  "${TARGET_DIR}/c5_physical_campaign.py" \
  "${TARGET_DIR}/c5_observation_probe.py" \
  "${TARGET_DIR}/memory_model.py" \
  "${TARGET_DIR}/memory_store.py" \
  "${TARGET_DIR}/memory_manager.py" \
  "${TARGET_DIR}/memory_retriever.py" \
  "${TARGET_DIR}/config_memory.py" \
  "${TARGET_DIR}/cognitive_cache.py" \
  "${TARGET_DIR}/config_cache.py" \
  "${TARGET_DIR}/unix_http.py" \
  "${TARGET_DIR}/voice_gate.py" \
  "${TARGET_DIR}/live_tts.py" \
  "${TARGET_DIR}/alsa_capture.py" \
  "${TARGET_DIR}/alsa_stream.py" \
  "${TARGET_DIR}/adaptive_noise_canceller.py" \
  "${TARGET_DIR}/utterance_capture.py" \
  "${TARGET_DIR}/streaming_vad.py" \
  "${TARGET_DIR}/whisper_stt.py" \
  "${TARGET_DIR}/voice_runtime.py" \
  "${TARGET_DIR}/chat_cli.py" \
  "${TARGET_DIR}/energy_vad.py" \
  "${TARGET_DIR}/adaptive_vad.py" \
  "${TARGET_DIR}/transcript_filter.py" \
  "${TARGET_DIR}/human_interaction.py" \
  "${TARGET_DIR}/human_context.py" \
  "${TARGET_DIR}/voice_daemon.py" \
  "${TARGET_DIR}/cli.py"

python3 -m json.tool "${TARGET_DIR}/config.json" >/dev/null
python3 -m json.tool "${TARGET_DIR}/observation_config.json" >/dev/null
python3 -m json.tool "${TARGET_DIR}/config_afetiva.json" >/dev/null
python3 -m json.tool "${TARGET_DIR}/config_percepcao.json" >/dev/null
python3 -m json.tool "${TARGET_DIR}/config_foco_emocao.json" >/dev/null
python3 -m json.tool "${TARGET_DIR}/config_affective_runtime.json" >/dev/null
python3 -m json.tool "${TARGET_DIR}/config_observation_affective.json" >/dev/null
python3 -m json.tool "${TARGET_DIR}/config_cognitiva.json" >/dev/null
python3 -m json.tool "${TARGET_DIR}/config_hermes.json" >/dev/null
python3 -m json.tool "${TARGET_DIR}/config_memory.json" >/dev/null
python3 -m json.tool "${TARGET_DIR}/config_cache.json" >/dev/null
python3 -m json.tool "${TARGET_DIR}/config_fast_router.json" >/dev/null
python3 -m json.tool "${TARGET_DIR}/config_voice.json" >/dev/null

echo "ATLAS_STATE_REACTION_INSTALL_PASS"
echo "ATLAS_OBSERVATION_INSTALL_PASS"
echo "ATLAS_SEMANTIC_S1_INSTALL_PASS"
echo "ATLAS_FAST_ROUTER_S2_INSTALL_PASS"
echo "ATLAS_FAST_DISPATCH_S3_INSTALL_PASS"
echo "ATLAS_D2_IDENTITY_PRESENCE_INSTALL_PASS"
echo "ATLAS_AFETIVO_A1_INSTALL_PASS"
echo "ATLAS_AFETIVO_A2_INSTALL_PASS"
echo "ATLAS_AFETIVO_A3_INSTALL_PASS"
echo "ATLAS_AFETIVO_A4_INSTALL_PASS"
echo "ATLAS_AFFECTIVE_RUNTIME_INSTALL_PASS"
echo "ATLAS_OBSERVATION_AFFECTIVE_PIPELINE_INSTALL_PASS"
echo "ATLAS_AFFECTIVE_BOOT_INSTALL_PASS"
echo "ATLAS_COGNITIVE_CONTEXT_BRIDGE_INSTALL_PASS"
echo "ATLAS_COGNITIVO_C1_INSTALL_PASS"
echo "ATLAS_COGNITIVO_C2_INSTALL_PASS"
echo "ATLAS_COGNITIVO_C3_INSTALL_PASS"
echo "ATLAS_COGNITIVO_C4_INSTALL_PASS"
echo "ATLAS_COGNITIVO_C5_HARNESS_INSTALL_PASS"
echo "ATLAS_COGNITIVO_C5_HARDENING_INSTALL_PASS"
echo "ATLAS_MEMORY_M1_INSTALL_PASS"
echo "ATLAS_COGNITIVE_CACHE_K1_INSTALL_PASS"
echo "ATLAS_COGNITIVE_CACHE_K2_INSTALL_PASS"
echo "ATLAS_I1_OBSERVATION_INTEGRATION_INSTALL_PASS"
install -d -m 0755 "${HOME}/.config/systemd/user"
install -m 0644 "${SOURCE_DIR}/atlas-observation.service" "${HOME}/.config/systemd/user/atlas-observation.service"
install -m 0644 "${SOURCE_DIR}/atlas-cognitive.service" "${HOME}/.config/systemd/user/atlas-cognitive.service"
install -m 0644 "${SOURCE_DIR}/atlas-voice.service" "${HOME}/.config/systemd/user/atlas-voice.service"
if systemctl --user show-environment >/dev/null 2>&1; then
  systemctl --user daemon-reload
  systemctl --user enable atlas-observation.service
  systemctl --user enable atlas-cognitive.service
  systemctl --user restart atlas-observation.service
  systemctl --user restart atlas-cognitive.service
fi

echo "ATLAS_COGNITIVE_RUNTIME_INSTALL_PASS"
echo "ATLAS_ACTION_PLAN_CHAT_INSTALL_PASS"
echo "ATLAS_V1_ALWAYS_ON_VOICE_INSTALL_PASS"
echo "run=cd ${TARGET_ROOT} && python3 -m atlas.cli --input <snapshot.json>"
