# Regras de Governança — DevEx HomeLab

## Proteção de Hardware e Controle de Escopo
1. O nó `pentium` (`homelab.control`) é estritamente reservado para observabilidade leve, heartbeat e sentinel determinístico.
2. Cargas pesadas de processamento (LLM, Whisper STT, TTS, compilações pesadas, renderização contínua) são terminantemente proibidas de executar diretamente no host do Pentium e devem ser alocadas em containers dedicados no `core` (`homelab.compute`).
3. Nenhuma feature adicional de automação ou subsistema experimental poderá ser promovida enquanto as issues fundacionais P0 (notadamente Issue #11 Backup/DR) permanecerem pendentes.
4. O empacotamento de artefatos de software deve ser 100% declarativo e atômico (container-first ou pyproject/pip). É proibido o uso de laços manuais de arquivos hardcoded em scripts bash para instalação em nós físicos.
