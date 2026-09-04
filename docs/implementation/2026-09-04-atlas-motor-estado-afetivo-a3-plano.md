# A3 — Percepção e Correlação — Plano de Implementação

> **Para execução com agentes:** usar `superpowers:subagent-driven-development` ou `superpowers:executing-plans`. Cada tarefa segue RED → GREEN → commit.

**Objetivo:** transformar `Stimulus` certificados em percepção operacional separada da saúde técnica e correlacionar indisponibilidades por dependência sem dupla contagem causal.

**Arquitetura:** a A3 adiciona um reducer de evidências, um adaptador explícito de `Stimulus`, um grafo determinístico e um correlacionador bounded. A saída é `EstadoPercepcao` e `IncidenteTecnico`; nenhum componente altera `TechnicalState`, `EstadoAfetivo`, foco ou emoção derivada.

**Stack técnica:** Python stdlib, `dataclasses`, `enum`, `datetime`, `json`, `pathlib`, `unittest`; sem dependência externa.

**Especificação:** `docs/implementation/2026-09-04-atlas-motor-estado-afetivo-design.md`

## Restrições globais

- Base obrigatória: A2 HEAD `9ef4d9d57dfb0108eef318824623453760e4fb2c`, Foundation CI GREEN.
- Estado técnico continua autoritativo e nunca é reclassificado pela A3.
- Um único ping, SSH ou source error não confirma perda de entidade.
- `source_error` significa perda da fonte de percepção, não morte do membro.
- Toda confiança fica em `0.0..1.0`; todos os históricos, listas e filas da A3 são bounded.
- Evidência explícita marcada como conclusiva pode abreviar confirmação.
- Correlação pode reduzir duplicidade causal, mas não apagar indisponibilidades observadas.
- A4 (foco/emoção), A5+ (agente/transporte) e A7 (diagnóstico ativo) ficam fora.
- Zero LLM, zero áudio, zero shell arbitrário e zero alteração de rede/systemd.

## Estrutura prevista

- `modelo_percepcao.py`: enums e contratos imutáveis de evidência/percepção.
- `percepcao.py`: política de confirmação e consolidação pura de evidências.
- `adaptador_stimulus_percepcao.py`: tradução conservadora de `Stimulus` para evidência.
- `grafo_dependencias.py`: dependências acíclicas e bounded.
- `modelo_incidente.py`: contrato imutável de incidente técnico.
- `correlacionador_incidentes.py`: seleção determinística de causa provável e anti-cascata.
- `pipeline_percepcao_correlacao.py`: consumo end-to-end de `Stimulus` e atualização de percepção/incidentes.
- `persistencia_percepcao_correlacao.py`: snapshot atômico versionado.
- `config_percepcao.json`: política, mapeamento de fontes e topologia inicial.

### Tarefa 1 — Contratos de percepção

**Produz:** `EstadoObservacao`, `ResultadoEvidencia`, `EvidenciaPercepcao`, `EstadoPercepcao`.

- [ ] RED em `tests/test_modelo_percepcao.py`: normalização UTC, confiança bounded, coleções imutáveis e estados `OBSERVADO`, `PARCIALMENTE_OBSERVADO`, `INACESSIVEL`, `DESCONHECIDO`.
- [ ] Executar `python -m unittest infrastructure.pentium.atlas.tests.test_modelo_percepcao -v` e confirmar falha por módulo ausente.
- [ ] Implementar `modelo_percepcao.py` sem lógica de correlação.
- [ ] Rodar teste específico e suíte completa.
- [ ] Commit: `feat(atlas): adicionar contratos de percepcao A3`.

### Tarefa 2 — Consolidação de evidências

**Produz:** `PoliticaConfirmacaoPercepcao` e `consolidar_percepcao(...)`.

- [ ] RED em `tests/test_percepcao.py`: nenhuma evidência → `DESCONHECIDO`; observação válida → `OBSERVADO`; uma indisponibilidade isolada → `PARCIALMENTE_OBSERVADO`; duas fontes independentes indisponíveis → `INACESSIVEL`; disponível + indisponível → conflito parcial; evidência conclusiva pode confirmar cedo.
- [ ] Confirmar RED.
- [ ] Implementar política configurável com `min_fontes_indisponiveis`, `confianca_conclusiva` e `max_evidencias`.
- [ ] Garantir truncamento determinístico das evidências mais recentes.
- [ ] Rodar teste específico e suíte completa.
- [ ] Commit: `feat(atlas): consolidar evidencias de percepcao A3`.

### Tarefa 3 — Adaptador de Stimulus

**Produz:** `ConfigFontePercepcao` e `evidencia_de_stimulus(...)`.

- [ ] RED em `tests/test_adaptador_stimulus_percepcao.py`.
- [ ] Provar que `source_error` vira `FONTE_INDISPONIVEL`, nunca `INACESSIVEL`.
- [ ] Provar que snapshot recebido mantém entidade observável mesmo se o estado técnico for `critical`, salvo evidência explícita de alcance.
- [ ] Provar que campos de alcance configurados (`tailscale_online`, `ssh_reachable`) podem produzir evidência disponível/indisponível.
- [ ] Implementar tradução conservadora e idempotente usando `stimulus_id` como `evidencia_id`.
- [ ] Rodar teste específico e suíte completa.
- [ ] Commit: `feat(atlas): adaptar stimulus para percepcao A3`.

### Tarefa 4 — Grafo de dependências

**Produz:** `GrafoDependencias`.

- [ ] RED em `tests/test_grafo_dependencias.py`: aresta duplicada idempotente, self-loop rejeitado, ciclo rejeitado, capacidade máxima respeitada e dependentes transitivos determinísticos.
- [ ] Confirmar RED.
- [ ] Implementar direção `dependente -> depende_de`, preservando a leitura lógica `Internet → modem → firewall → membros`.
- [ ] Rodar teste específico e suíte completa.
- [ ] Commit: `feat(atlas): adicionar grafo de dependencias A3`.

### Tarefa 5 — Incidentes e anti-cascata

**Produz:** `IncidenteTecnico`, `EstadoRecuperacaoIncidente`, `CorrelacionadorIncidentes`.

- [ ] RED em `tests/test_correlacionador_incidentes.py`.
- [ ] Cenário firewall indisponível + Core/x99 indisponíveis → um incidente principal no firewall, membros como efeitos correlacionados.
- [ ] Cenário Internet indisponível com firewall/Core/x99 observados → incidente principal externo, sem colapso do corpo distribuído.
- [ ] Cenário host + muitos projetos indisponíveis → um incidente principal, listas truncadas por orçamento e contadores totais preservados.
- [ ] Recuperação do root encerra o incidente sem alterar `EstadoPercepcao` dos dependentes.
- [ ] Implementar causa provável pelo ancestral indisponível com maior cobertura; desempate lexical e confiança causal bounded.
- [ ] Rodar teste específico e suíte completa.
- [ ] Commit: `feat(atlas): correlacionar incidentes sem cascata A3`.

### Tarefa 6 — Pipeline end-to-end

**Produz:** `PipelinePercepcaoCorrelacao`.

- [ ] RED em `tests/test_pipeline_percepcao_correlacao.py`.
- [ ] Consumir `Stimulus` sem mutar o objeto de entrada nem `TechnicalState`.
- [ ] Deduplicar `stimulus_id`, manter histórico de evidências bounded por entidade, recalcular `EstadoPercepcao` e atualizar incidentes.
- [ ] Provar fluxo `source_error` isolado → percepção parcial sem incidente de perda.
- [ ] Provar duas evidências independentes de indisponibilidade → percepção confirmada e incidente correlacionado.
- [ ] Implementar `config_percepcao.json` com política e topologia inicial Pentium/Core/x99/firewall/modem/Internet.
- [ ] Rodar teste específico e suíte completa.
- [ ] Commit: `feat(atlas): integrar pipeline de percepcao e correlacao A3`.

### Tarefa 7 — Persistência, empacotamento e certificação

**Produz:** snapshot A3 e gate `DEVEX_HOMELAB_ATLAS_AFETIVO_A3_PASS`.

- [ ] RED em `tests/test_persistencia_percepcao_correlacao.py` e `tests/test_a3_empacotamento.py`.
- [ ] Persistir percepções e incidentes abertos em JSON versão 1 com escrita atômica; corrupção restaura vazio com erro explícito.
- [ ] Incluir módulos/config A3 no `install-user.sh` sem ativar serviço.
- [ ] Incluir `py_compile`, JSON validation, suíte e marcador A3 no Foundation CI.
- [ ] Rodar suíte completa, `git diff --check` e validação de shell do blob LF do HEAD.
- [ ] Commit: `ci(atlas): certificar percepcao e correlacao A3`.
- [ ] Push e abrir PR Draft sobre `atlas/issue-20-entidades-vinculos-expectativas`; só considerar GREEN se CI concluir `success` no HEAD exato.

## Autorrevisão

A3 cobre percepção separada da saúde, confirmação temporal, evidência conflitante, grafo, causalidade, anti-cascata, tempestade bounded, recuperação e persistência. Não há implementação de foco/emoção, diagnóstico ativo, agente, transporte, LLM ou controle remoto.
