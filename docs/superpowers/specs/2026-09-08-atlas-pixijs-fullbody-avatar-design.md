# Atlas Avatar v1.1 — Full-body PixiJS

## Contexto

Esta especificação complementa a especificação `2026-09-04-atlas-avatar-v1-design.md` e registra a evolução aprovada do renderer visual do Atlas. O contrato de estado visual, a autoridade do Motor de Estado Afetivo e a separação entre observação, cognição e apresentação permanecem válidos. A mudança desta slice é exclusivamente de apresentação e animação no dashboard.

A identidade visual oficial continua baseada no personagem aprovado: estilo anime, cabelo longo violeta/roxo-escuro, olhos verdes, camisa branca e roupa azul-escura. O avatar deve ser reconhecível como o mesmo personagem em todos os estados.

## Decisão arquitetural

O renderer principal deixa de ser SVG por camadas e passa a ser **PixiJS 2D full-body com rig articulado**. O navegador continua responsável pela renderização; o Pentium fornece apenas estado visual derivado.

```text
Motor de Estado Afetivo / Cognição / Foco
                 ↓
         EstadoVisualAtlas
                 ↓
      AdaptadorVisualDashboard
                 ↓
        AtlasAvatarEngine
          (PixiJS 2D)
                 ↓
      Rig + Animator + Assets
                 ↓
            Dashboard
```

O renderer não consulta diretamente o Motor de Estado Afetivo, não decide emoção, não executa comandos e não altera estado técnico.

## Objetivos da slice

- substituir a apresentação estática/SVG pelo avatar full-body aprovado;
- animar rosto, cabeça, braços e mãos;
- preservar o contrato `EstadoVisualAtlas` como entrada autoritativa;
- permitir estados `ocioso`, `observando`, `conversando` e `reagindo`;
- suportar expressões `sereno`, `engajado`, `curioso`, `atento`, `preocupado`, `sob_pressao` e `recuperando`;
- manter fallback seguro quando PixiJS, assets ou WebGL falharem;
- manter dashboard read-only em relação ao estado afetivo e ao homelab.

## Fora de escopo

- 3D;
- Live2D proprietário;
- captura facial;
- motion capture;
- reconhecimento facial;
- sincronização fonética avançada;
- física de cabelo ou roupa de alta complexidade;
- mudança automática de roupa ou identidade visual;
- geração de emoção pelo renderer.

## Rig 2D

O personagem será separado em peças com pivôs e hierarquia explícitos:

```text
root
├── pelvis/tronco
│   ├── peito
│   ├── pescoco
│   │   └── cabeca
│   │       ├── cabelo_frente
│   │       ├── cabelo_tras
│   │       ├── olhos
│   │       ├── sobrancelhas
│   │       └── boca
│   ├── ombro_esq
│   │   └── braco_esq
│   │       └── antebraco_esq
│   │           └── mao_esq
│   └── ombro_dir
│       └── braco_dir
│           └── antebraco_dir
│               └── mao_dir
└── pernas/base_visual
```

Os pivôs devem permitir rotação natural de ombros, cotovelos, pulsos, cabeça e tronco. A primeira versão não exige IK completo; poses compostas são suficientes desde que os membros mantenham continuidade visual.

## AtlasAvatarEngine

Responsabilidades:

- inicializar PixiJS e o canvas;
- carregar o atlas de texturas;
- construir o rig;
- receber somente `EstadoVisualAtlas` normalizado;
- manter um state machine visual;
- interpolar poses e parâmetros de expressão;
- executar idle animation;
- coordenar rosto, olhar, boca, cabeça, braços e mãos;
- limitar frequência e amplitude de gestos;
- expor telemetria mínima de renderer para o dashboard;
- cair para fallback sem interromper o restante da página.

O engine não pode conter regras de saúde de infraestrutura, classificação afetiva, policy cognitiva ou autorização operacional.

## Estado visual de entrada

O contrato existente permanece compatível. O adaptador pode enriquecer a representação local com campos derivados exclusivamente para renderização:

```text
EstadoVisualAtlas
├── modo
├── expressao
├── intensidade_expressao
├── foco_visual
├── direcao_olhar
├── gesto_atual
├── velocidade_movimento
├── intensidade_movimento
├── falando
├── ouvindo
├── pensando
├── duvida_identidade
└── transicao_ms
```

Nenhum novo campo visual se torna fonte de verdade persistente.

## Face

A face deve suportar:

- piscar natural com temporização pseudoaleatória bounded;
- direção de pupila horizontal/vertical limitada;
- abertura de olhos;
- inclinação de sobrancelhas;
- estados discretos de boca;
- sorriso leve, neutro, sério, dúvida e alívio;
- inclinação e micro-rotação da cabeça.

Lip-sync v1 usa amplitude/estado de fala, não análise fonética. Quando `falando=false`, a boca retorna ao estado compatível com a expressão.

## Braços e mãos

Gestos mínimos obrigatórios:

- aceno curto;
- apontar para elemento do dashboard;
- mão próxima ao rosto em estado curioso/dúvida;
- postura aberta durante engajamento;
- braços mais contidos em preocupação/sob pressão;
- relaxamento progressivo em recuperação;
- gesto de escuta durante `ouvindo=true`.

Gestos possuem prioridade inferior a eventos críticos. Uma reação crítica pode interromper um gesto ocioso ou social.

## State machine visual

Estados de alto nível:

```text
BOOT
→ IDLE
→ OBSERVING
→ LISTENING
→ THINKING
→ SPEAKING
→ REACTING
→ RECOVERING
→ IDLE/OBSERVING
```

`EstadoVisualAtlas.modo` e flags de conversa determinam transições permitidas. O renderer não inventa estado ausente.

Prioridade visual:

```text
REACTING crítico
> SPEAKING / LISTENING / THINKING
> OBSERVING
> gesto explícito
> idle
```

## Idle animation

Quando o Atlas está ocioso:

- respiração sutil no tronco;
- piscar natural;
- micro movimento de cabeça;
- pequena transferência de postura;
- movimento muito leve do cabelo;
- gesto ocasional bounded.

Idle não pode competir visualmente com dados do dashboard nem produzir movimento contínuo excessivo.

## Integração com o dashboard

O canvas PixiJS fica em um componente isolado do restante da interface. O componente recebe snapshot visual já normalizado e não faz polling próprio do estado afetivo.

Estrutura lógica prevista:

```text
dashboard/
├── avatar/
│   ├── AtlasAvatarEngine
│   ├── AtlasRig
│   ├── AtlasAnimator
│   ├── AtlasExpressionController
│   ├── AtlasGestureController
│   ├── AtlasAssetLoader
│   └── AtlasAvatarFallback
└── state/
    └── adaptador-estado-visual
```

Os nomes finais podem seguir a estrutura real existente do projeto, preservando essas fronteiras.

## Assets

A imagem aprovada é referência visual, não um sprite monolítico obrigatório. Para animação articulada, os assets devem ser preparados em camadas com transparência e alinhamento consistente.

Requisitos:

- manter cabelo longo violeta/roxo-escuro;
- manter olhos verdes;
- manter camisa branca e vestido/roupa azul-escura;
- preservar proporções e identidade facial;
- separar no mínimo rosto, cabelo, olhos, boca, tronco, braços, antebraços e mãos;
- evitar reconstrução visual que descaracterize o personagem aprovado.

## Performance

Alvos iniciais:

- 60 FPS quando a máquina/navegador suportar;
- degradação aceitável até 30 FPS;
- atualização de estado desacoplada do frame loop;
- nenhuma requisição de rede por frame;
- assets carregados uma única vez e reutilizados;
- animações calculadas no cliente;
- pausa ou redução de animação quando a aba não estiver visível;
- respeito a `prefers-reduced-motion` com modo de movimento reduzido.

## Fallback e falhas

Se PixiJS não inicializar, WebGL/canvas falhar ou asset obrigatório não carregar:

1. registrar falha do renderer;
2. interromper somente o engine visual;
3. apresentar fallback 2D estático reconhecível;
4. manter todos os demais cards, dados e controles do dashboard operacionais;
5. nunca propagar erro visual para Atlas Core, cognição, observação ou voz.

## Segurança e isolamento

O renderer não recebe:

- áudio bruto;
- credenciais;
- tokens;
- biometria;
- comandos de shell;
- acesso direto a serviços do homelab.

Ele consome somente estado visual derivado e assets locais/versionados.

## Testes

### Unidade

- normalização de `EstadoVisualAtlas`;
- prioridades da state machine;
- clamp de intensidade, velocidade e transição;
- seleção de expressão;
- interrupção de gesto por reação crítica;
- fallback após erro de asset/renderer.

### Integração

- snapshot recebido pelo dashboard altera pose/expressão esperada;
- `ouvindo`, `pensando` e `falando` não conflitam;
- mudança de foco move olhos sem trocar emoção indevidamente;
- estado `sob_pressao` reduz gestos ociosos;
- recuperação retorna de forma gradual.

### Visual

- personagem continua reconhecível em todos os arquétipos;
- braços e mãos não se desconectam do rig nas poses obrigatórias;
- cabeça, olhos e boca permanecem alinhados durante transições;
- fallback funciona sem quebrar layout;
- dashboard continua legível em resoluções alvo.

## Critérios de aceite

A slice é considerada concluída quando:

1. o dashboard renderiza o personagem aprovado como avatar full-body em PixiJS;
2. rosto, cabeça, braços e mãos possuem animação funcional;
3. `EstadoVisualAtlas` continua sendo a única entrada comportamental do renderer;
4. os estados principais e sete arquétipos visuais são demonstráveis;
5. `ouvindo`, `pensando` e `falando` têm comportamentos distintos;
6. pelo menos os gestos de aceno, apontar, dúvida e escuta estão funcionais;
7. renderer e assets possuem fallback seguro;
8. falha visual não afeta Atlas Core nem os dados do dashboard;
9. testes unitários, integração e validação visual da slice estão verdes;
10. a imagem/personagem aprovado permanece reconhecível após o recorte em camadas e rigging.

## Migração da especificação anterior

A especificação v1 anterior permanece autoritativa para identidade visual, semântica de `EstadoVisualAtlas`, modos comportamentais, arquétipos e isolamento. Esta v1.1 substitui apenas as decisões que especificavam `renderer = svg_camadas` e o rig mínimo SVG.

Novo identificador:

```text
versao_avatar = 1.1
identidade_visual = atlas
renderer = pixijs_2d_fullbody
```

## Ordem segura de implementação

1. localizar e isolar o componente atual do avatar no dashboard;
2. criar testes do adaptador e state machine antes do engine;
3. integrar PixiJS sem substituir ainda o fallback;
4. preparar assets do personagem aprovado em camadas;
5. implementar rig e animação facial;
6. implementar braços, mãos e gestos;
7. ligar `EstadoVisualAtlas` ao engine;
8. validar performance e reduced-motion;
9. executar certificação visual no dashboard físico;
10. somente depois remover o caminho SVG primário, mantendo fallback estático seguro.
