# Atlas Dashboard Cognitive Panel Design

## Objetivo
Expor no dashboard LAN do Pentium uma visão read-only do contexto observacional/cognitivo certificado do Atlas, sem permitir que dashboard/browser alterem A1/A2/A3/A4, cognição, voz ou serviços.

## Base
A slice parte do SHA certificado `e3f4723777107ee654e3ce69c40e04978000201a` da branch `atlas/issue-20-observation-cognitive-context`.

## Arquitetura
O browser continua consumindo apenas os endpoints HTTP do dashboard. O dashboard backend lê `~/pentium-agent/atlas/runtime/cognitive-observation-context.json` e `observation-affective-health.json`, valida o snapshot e publica uma projeção visual própria em `/api/status`.

Fluxo:
`A1/A3/A4 -> cognitive-observation-context.json -> dashboard_collectors.py -> /api/status -> dashboard.html`.

O dashboard nunca lê objetos vivos nem chama `ReactionLoopCognitivo`; é observabilidade somente leitura.
## Dados exibidos
A seção `cognition` de `/api/status` terá estado `available`, `stale` ou `unavailable`, idade do snapshot, SHA esperado/observado, entidade, percepção, confiança, emoção, foco, último stimulus e dimensões A1.

Dimensões A1 exibidas: valência, ativação, estresse, confiança, engajamento e curiosidade, normalizadas apenas para apresentação percentual. O valor bruto continua disponível no payload read-only.

A3 exibirá `entity_id`, estado perceptivo, confiança, conflito de evidências e incidente relevante quando existir. A4 exibirá emoção principal, nuances e foco principal.

`recent_changes` será resumido no backend para no máximo 8 eventos com `timestamp`, `source`, `kind`, `severity` e `stimulus_id`. Nenhum payload arbitrário será enviado ao browser.

## Freshness e falhas
O dashboard usará o mesmo limite cognitivo de 180 segundos. Snapshot ausente/corrompido/schema inválido/SHA incompatível gera `unavailable`; snapshot válido porém acima de 180s gera `stale`.

Falha cognitiva nunca derruba `/api/status`. Os demais cards continuam disponíveis. Não haverá fallback afetivo sintético: quando contexto não estiver disponível, a UI mostra explicitamente `CONTEXTO INDISPONÍVEL`.
## UI: Mente do Atlas
A seção fica integrada ao card do avatar e abaixo dele, sem criar uma segunda aplicação. Exibe headline de disponibilidade, pipeline `Percepção -> Afeto -> Foco/Emoção -> Contexto Cognitivo`, cards de A1, A3 e A4 e uma lista curta de mudanças recentes.

Estados visuais: `available` usa apresentação normal, `stale` mostra aviso explícito de contexto antigo, `unavailable` mostra o painel em modo degradado. O avatar continua sendo governado exclusivamente por `visual-state.json`; cognição não substitui nem força expressão/modo visual.

O refresh continua em 2 segundos e usa o `/api/status` existente. Não será criado novo endpoint nesta slice.

## Segurança e ownership
- HTTP permanece bindado somente em `192.168.88.3:8765`.
- Métodos de escrita continuam 405.
- Browser não recebe transcript, áudio, prompts, tokens, secrets nem payload cru de Stimulus.
- Dashboard não escreve runtime files nem executa capabilities.
- Voz permanece `inactive/disabled` e não é alterada por instalação/deploy desta slice.
- Nenhuma mudança em L2jToren.

## Arquivos previstos
Modificar `dashboard_collectors.py`, `dashboard.html`, `config.json`, testes do dashboard e packaging/installer apenas se necessário para os novos caminhos configuráveis.
## Testes e gates
TDD RED→GREEN deve cobrir leitura/validação do snapshot, freshness, SHA mismatch, ausência de fallback sintético, sanitização de `recent_changes`, integração de `cognition` em `collect_status`, renderização dos estados available/stale/unavailable e preservação dos métodos HTTP read-only.

Regressão obrigatória: 508+ testes Atlas existentes, suíte completa do dashboard, `py_compile`, JSON, `bash -n`, `git diff --check` e UTF-8.

## Deploy e certificação no Pentium
No SHA exato da slice:
1. dashboard service active;
2. observation service active e voice inactive/disabled;
3. `/api/status` retorna `cognition.status=available` com SHA e entidade `x99` quando snapshot atual estiver válido;
4. UI LAN renderiza A1/A3/A4 e pipeline cognitivo sem console/runtime error;
5. cópia stale/invalid usada em teste isolado produz estado stale/unavailable sem derrubar outros cards;
6. nenhuma requisição HTTP de escrita passa a ser aceita.

Marker final proposto: `ATLAS_DASHBOARD_COGNITIVE_PANEL_PHYSICAL_PASS`.

## Fora de escopo
Chat no dashboard, execução de capabilities, ativação cognitiva autônoma, reativação de voz, edição de estado afetivo, histórico persistente adicional e qualquer controle remoto pelo browser.