# Atlas C5 — Certificação Cognitiva E2E

## Objetivo

Preparar e executar a certificação física do caminho cognitivo C1→C4 no Pentium real, sem transformar CI em evidência física.

## Slice de implementação

1. `CertificadorCognitivo` mede amostras antes/depois, latência e resultado da inferência.
2. `LinuxCognitiveSampler` coleta RSS, swap, CPU e temperatura com fontes Linux bounded.
3. Installer empacota apenas o harness.
4. Foundation CI valida código/testes e emite somente `DEVEX_HOMELAB_ATLAS_COGNITIVO_C5_HARNESS_PASS`.
5. `ATLAS_COGNITIVO_C5_PHYSICAL_PASS` é proibido em CI e installer.

## Gate físico

A certificação final exige execução no Pentium real com backend/modelo selecionados, preservação do Observation Runtime e evidência do mesmo SHA.
