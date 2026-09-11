# Atlas Affective Runtime + Compositor Visual — Design

## Objetivo
Criar o owner runtime autoritativo do estado afetivo do Atlas no Pentium e conectar esse estado ao Avatar v1 sem permitir que dashboard, voz, LLM ou health inventem emoção.

Base funcional: `f20a2d46202733ece27d59a9313026ef73ee7a54`, onde o dashboard já consome `EstadoVisualAtlas` via `runtime/visual-state.json`.

## Problema atual
A1–A4 já fornecem domínio e persistência para `EstadoAfetivo`, foco e emoção derivada, porém não existe um processo de produção que mantenha esses componentes vivos continuamente.

O `HumanContextProvider` da voz sintetiza contexto afetivo mínimo a partir do health e não pode ser promovido a fonte autoritativa do avatar.

Consequências atuais:
- o dashboard possui renderer e fallback, mas não recebe estado visual vivo;
- `MotorEstadoAfetivo` e `ContextoFocoEmocao` existem sem owner contínuo;
- voz possui estados efêmeros, mas não há composição unificada com o avatar;
- não existe single writer formal para `visual-state.json`.

## Decisão arquitetural
Introduzir `AffectiveRuntime` como owner exclusivo do ciclo afetivo/visual no Pentium.

```text
Observation Runtime / eventos semânticos
              ↓
      AffectiveRuntime (owner)
        ↙             ↘
MotorEstadoAfetivo  ContextoFocoEmocao
        ↘             ↙
      ResultadoFocoEmocao
              ↓
   CompositorVisualAfetivo
      EstadoVisualAtlas
              ↓
   VisualStatePublisher
              ↓
 runtime/visual-state.json
              ↓
      Dashboard / Avatar
```

O runtime é determinístico, bounded e sem LLM. O compositor visual é projeção: não altera estado afetivo, foco, saúde técnica ou percepção.

## Ownership e fontes de verdade
- `MotorEstadoAfetivo`: autoridade das seis dimensões afetivas.
- `ContextoFocoEmocao`: autoridade da projeção de foco e emoção derivada.
- Observation Runtime/correlacionadores: autoridade dos sinais técnicos e semânticos recebidos.
- `AffectiveRuntime`: coordena leitura, atualização, restauração e publicação sem redefinir a verdade técnica.
- `CompositorVisualAfetivo`: converte estado afetivo + foco + emoção + interação efêmera em `EstadoVisualAtlas`.
- `VisualStatePublisher`: único writer de `runtime/visual-state.json`.
- Dashboard: consumidor exclusivamente read-only.
- Voz: publica presença efêmera, nunca escreve diretamente no snapshot visual.
- LLM: não escreve em dimensões afetivas e não escolhe expressão ou gesto.

## Contrato EstadoVisualAtlas
O contrato materializa a especificação já aprovada do Avatar v1:

```text
versao_avatar = 1
modo, expressao, intensidade_expressao
foco_visual, direcao_olhar, gesto_atual
velocidade_movimento, intensidade_movimento
falando, ouvindo, pensando, duvida_identidade
transicao_ms
```
Validações obrigatórias:
- intensidades e velocidades em `0.0..1.0`;
- `transicao_ms` em `120..1500`;
- enums fechados para modo e expressão;
- ausência de foco resulta em `neutro`;
- dados inválidos nunca derrubam Observation Runtime ou dashboard.

## Política de composição visual v1
Mapeamento determinístico inicial:
- `calmo`, `confiante`, `satisfeito` → `SERENO`;
- `interessado` → `ENGAJADO`;
- `curioso` → `CURIOSO`;
- `atento`, `vigilante` → `ATENTO`;
- `preocupado` → `PREOCUPADO`;
- `estressado`, `alarmado`, `frustrado` → `SOB_PRESSAO`;
- `aliviado` ou recuperação relevante → `RECUPERANDO`.

A intensidade visual é uma função bounded das dimensões relevantes, nunca de um threshold isolado.

## Modos comportamentais
Prioridade:
1. `falando` → `CONVERSANDO`;
2. `pensando` → `CONVERSANDO`;
3. `ouvindo` → `CONVERSANDO`;
4. evento crítico/reação transitória → `REAGINDO`;
5. foco principal existente → `OBSERVANDO`;
6. caso contrário → `OCIOSO`.

Estados efêmeros de interação jamais alteram o vetor afetivo; apenas modulam a projeção visual.

## Foco, olhar e gestos
- `foco_visual` usa `FocoAtencao.principal.entidade_id`; sem foco, usa `neutro`.
- `direcao_olhar` deriva apenas do foco já resolvido; não executa descoberta nem diagnóstico.
- gestos v1: `nenhum`, `escuta`, `pensamento`, `fala`, `duvida`, `surpresa`, `alivio`.
- gesto não dispara ações operacionais.

## Estado efêmero de interação
Contrato separado `EstadoInteracaoVisual`:

```text
ouvindo: bool
pensando: bool
falando: bool
duvida_identidade: bool
degradado: bool
atualizado_em: timestamp UTC
```

Esse estado não é memória emocional. Reinício limpa flags e recompõe o avatar a partir do estado afetivo/foco atuais.

## Restauração e retomada
No start do `AffectiveRuntime`:
1. carregar `PersonalidadeBase` e política A1;
2. restaurar `EstadoAfetivo` com decaimento offline;
3. restaurar A4 apenas como contexto auxiliar válido;
4. reconstruir foco/emoção da realidade atual conforme eventos recentes;
5. compor novo `EstadoVisualAtlas`;
6. publicar um snapshot visual novo.

Snapshot visual antigo nunca é fonte de verdade e nunca é restaurado como emoção.
## Publicação atômica
`VisualStatePublisher` deve:
- criar diretório runtime quando necessário;
- serializar JSON versionado;
- escrever em temporário no mesmo diretório;
- executar `flush` + `fsync`;
- usar `os.replace` atômico;
- fsync do diretório em POSIX quando disponível;
- remover temporário em falha;
- nunca manter fila de snapshots visuais.

Arquivo canônico: `~/pentium-agent/atlas/runtime/visual-state.json`.

## Loop e orçamento
- sem busy loop;
- fonte dirigida por evento ou tick limitado e configurável;
- fila bounded;
- coalescing permitido para visuais superseded;
- nenhuma chamada de LLM para atualizar visual;
- nenhuma escrita em disco por frame de animação;
- publicar apenas em mudança material ou heartbeat visual espaçado;
- falha de publicação não bloqueia o estado afetivo em memória.

## Integração com voz
A voz não vira owner afetivo. Transições efêmeras:
- captura aguardando → `ouvindo=true`;
- STT/LLM/processamento → `pensando=true`;
- TTS → `falando=true`;
- exceção de voz → `degradado=true`, sem inventar estresse.

O transporte interno deve ser local, pequeno e bounded, mantendo um único writer visual.
## Integração com Observation Runtime
`AffectiveRuntime` recebe eventos semânticos já interpretados, não telemetria bruta. O adaptador respeita percepção/correlação existentes e só produz `ImpulsoAfetivo` pelas políticas aprovadas.

A conexão física completa com todas as fontes pode ser fatiada após a fundação do runtime. O runtime deve ser testável com fonte injetável.

## Falhas e isolamento
- erro no compositor → último visual válido ou fallback, sem alterar afeto;
- erro no publisher → registrar e continuar domínio em memória;
- snapshot A1 inválido → personalidade base + retomada A1;
- snapshot A4 inválido → ignorar contexto derivado e recompor;
- voz indisponível → flags efêmeras desligadas/degradadas;
- dashboard indisponível → nenhum impacto no runtime;
- LLM indisponível → nenhum impacto na composição determinística.

## Segurança
Proibido:
- CONTROL/DESTRUCTIVE ou shell arbitrário;
- escrita em health/percepção técnica pelo compositor;
- dashboard como input de estado;
- LLM escolhendo emoção, foco, severidade, gesto ou expressão;
- áudio bruto, transcrição completa ou biometria no `visual-state.json`;
- filas/históricos visuais ilimitados ou gravação por frame.

## Arquivos previstos
Novos:
- `modelo_visual_atlas.py`;
- `compositor_visual_afetivo.py`;
- `visual_state_publisher.py`;
- `affective_runtime.py`;
- testes unitários correspondentes.

Alterados: `install-user.sh`, configuração runtime versionada e `foundation-ci.yml`; integrações de voz/observation entram somente após contratos do runtime GREEN.
## Estratégia TDD
Ordem:
1. `EstadoVisualAtlas` e validações;
2. compositor emoção/foco → expressão/modo/intensidade;
3. publisher atômico;
4. runtime com restauração A1/A4 e source injetável;
5. estado efêmero de interação;
6. empacotamento e gate CI;
7. integração física incremental com voz/Observation Runtime.

Cada comportamento nasce de teste RED observado antes do código de produção.

## Critérios de conclusão
A fundação estará concluída no HEAD exato quando:
- existir exatamente um owner/writer do estado visual;
- `EstadoVisualAtlas` estiver validado e bounded;
- expressão for derivada deterministicamente sem LLM;
- foco visual vier de `FocoAtencao` resolvido;
- voz apenas modular flags efêmeras;
- snapshot visual for atômico e nunca restaurado como verdade emocional;
- corrupção/ausência de snapshots não derrubar o runtime;
- dashboard consumir o snapshot produzido sem mudança de autoridade;
- testes, `py_compile`, JSON, `bash -n` e `git diff --check` estiverem GREEN;
- gate CI específico estiver GREEN no mesmo SHA.

## Fora de escopo
- reconhecimento facial/biométrico;
- aprendizagem de personalidade;
- LLM alterando emoção;
- animação 3D;
- controle de infraestrutura;
- persistência do último rosto/pose;
- telemetria bruta no compositor;
- qualquer mudança de contratos do L2jToren.
