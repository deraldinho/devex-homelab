#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_ROOT="${HOME}/pentium-agent"
TARGET_DIR="${TARGET_ROOT}/atlas"

install -d -m 0755 "${TARGET_DIR}"

for file in \
  __init__.py \
  state_model.py \
  health_engine.py \
  reaction_engine.py \
  journal.py \
  stimulus_model.py \
  stimulus_bus.py \
  stimulus_journal.py \
  network_discovery.py \
  network_discovery_smoke.py \
  presence_registry.py \
  presence_persistence.py \
  stimulus_sources.py \
  observation_runtime.py \
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
  modelo_contexto_cognitivo.py \
  configuracao_cognitiva.py \
  contexto_cognitivo.py \
  politica_ativacao_cognitiva.py \
  modelo_llm_gateway.py \
  configuracao_llm.py \
  llm_gateway.py \
  llama_cpp_backend.py \
  reaction_loop_cognitivo.py \
  capability_registry.py \
  policy_capabilities.py \
  saida_cognitiva.py \
  cli.py; do
  install -m 0644 "${SOURCE_DIR}/${file}" "${TARGET_DIR}/${file}"
done

for config in config.json observation_config.json config_afetiva.json config_percepcao.json config_foco_emocao.json config_cognitiva.json config_llm.json; do
  install -m 0644 "${SOURCE_DIR}/${config}" "${TARGET_DIR}/${config}"
done

python3 -m py_compile \
  "${TARGET_DIR}/state_model.py" \
  "${TARGET_DIR}/health_engine.py" \
  "${TARGET_DIR}/reaction_engine.py" \
  "${TARGET_DIR}/journal.py" \
  "${TARGET_DIR}/stimulus_model.py" \
  "${TARGET_DIR}/stimulus_bus.py" \
  "${TARGET_DIR}/stimulus_journal.py" \
  "${TARGET_DIR}/network_discovery.py" \
  "${TARGET_DIR}/network_discovery_smoke.py" \
  "${TARGET_DIR}/presence_registry.py" \
  "${TARGET_DIR}/presence_persistence.py" \
  "${TARGET_DIR}/stimulus_sources.py" \
  "${TARGET_DIR}/observation_runtime.py" \
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
  "${TARGET_DIR}/modelo_contexto_cognitivo.py" \
  "${TARGET_DIR}/configuracao_cognitiva.py" \
  "${TARGET_DIR}/contexto_cognitivo.py" \
  "${TARGET_DIR}/politica_ativacao_cognitiva.py" \
  "${TARGET_DIR}/modelo_llm_gateway.py" \
  "${TARGET_DIR}/configuracao_llm.py" \
  "${TARGET_DIR}/llm_gateway.py" \
  "${TARGET_DIR}/llama_cpp_backend.py" \
  "${TARGET_DIR}/reaction_loop_cognitivo.py" \
  "${TARGET_DIR}/capability_registry.py" \
  "${TARGET_DIR}/policy_capabilities.py" \
  "${TARGET_DIR}/saida_cognitiva.py" \
  "${TARGET_DIR}/cli.py"

python3 -m json.tool "${TARGET_DIR}/config.json" >/dev/null
python3 -m json.tool "${TARGET_DIR}/observation_config.json" >/dev/null
python3 -m json.tool "${TARGET_DIR}/config_afetiva.json" >/dev/null
python3 -m json.tool "${TARGET_DIR}/config_percepcao.json" >/dev/null
python3 -m json.tool "${TARGET_DIR}/config_foco_emocao.json" >/dev/null
python3 -m json.tool "${TARGET_DIR}/config_cognitiva.json" >/dev/null
python3 -m json.tool "${TARGET_DIR}/config_llm.json" >/dev/null

echo "ATLAS_STATE_REACTION_INSTALL_PASS"
echo "ATLAS_OBSERVATION_INSTALL_PASS"
echo "ATLAS_D2_IDENTITY_PRESENCE_INSTALL_PASS"
echo "ATLAS_AFETIVO_A1_INSTALL_PASS"
echo "ATLAS_AFETIVO_A2_INSTALL_PASS"
echo "ATLAS_AFETIVO_A3_INSTALL_PASS"
echo "ATLAS_AFETIVO_A4_INSTALL_PASS"
echo "ATLAS_COGNITIVO_C1_INSTALL_PASS"
echo "ATLAS_COGNITIVO_C2_INSTALL_PASS"
echo "ATLAS_COGNITIVO_C3_INSTALL_PASS"
echo "ATLAS_COGNITIVO_C4_INSTALL_PASS"
echo "run=cd ${TARGET_ROOT} && python3 -m atlas.cli --input <snapshot.json>"
