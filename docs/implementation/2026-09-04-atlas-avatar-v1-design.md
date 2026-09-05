# Atlas Avatar v1 — Especificação de Design

## Contexto e objetivo

Esta especificação formaliza a identidade visual e o contrato comportamental do avatar do Atlas no DevEx HomeLab. O avatar é a presença visual do Atlas e traduz, de forma consistente e limitada, o estado afetivo, o foco de atenção e o contexto de interação produzidos pelos componentes autoritativos do sistema.

A aparência aprovada usa estilo anime, cabelo longo violeta/roxo-escuro, olhos verdes, expressão acolhedora e roupa azul-escura com camisa branca. Essa identidade deve permanecer reconhecível entre estados, telas e versões. A imagem de referência fornecida durante a definição arquitetural orienta os assets; esta especificação textual define os requisitos canônicos necessários para implementação e teste.

O avatar não é autoridade técnica, não diagnostica infraestrutura, não altera o estado afetivo e não executa comandos. A verdade técnica continua pertencendo aos componentes de observação e correlação; a verdade afetiva continua pertencendo ao Motor de Estado Afetivo.

## Base de integração

- iniciativa: Issue #20 / Atlas Local Intelligence;
- base funcional imediatamente anterior: A1 Núcleo Afetivo;
- branch desta especificação: `atlas/issue-20-avatar-v1`;
- idioma canônico para novos contratos, documentação, testes e checkpoints: português do Brasil;
- identificadores técnicos novos: português sem acentos quando necessário por compatibilidade;
- nenhum merge ou promoção de PR é autorizado por esta especificação.

## Escopo da versão 1

A primeira versão cobre:

- identidade visual estável do Atlas;
- contrato `EstadoVisualAtlas`;
- quatro modos comportamentais;
- sete arquétipos visuais derivados;
- intensidade contínua de expressão;
- foco visual e direção do olhar;
- animação ociosa;
- gestos mínimos e limitados;
- comportamento em conversa;
- reação visual a eventos relevantes;
- sinal visual de dúvida de identidade;
- despertar inicial e boot normal;
- transições suaves e histerese visual;
- fallback seguro em caso de falha visual;
- renderer 2D leve em SVG por camadas;
- separação entre estado interno, estado técnico e expressão externa.

Ficam fora desta versão:

- reconhecimento facial;
- captura ou processamento biométrico bruto dentro do avatar;
- decisão de identidade;
- autorização operacional;
- diagnóstico técnico;
- controle do homelab;
- geração de emoção por LLM;
- renderização de vídeo no servidor;
- catálogo extenso de roupas, personagens ou skins;
- simulação física complexa;
- alteração de personalidade pelo próprio avatar;
- câmera e visão computacional.

## Princípios de arquitetura

1. **Estado técnico autoritativo.** O avatar nunca reclassifica saúde de equipamento, serviço, rede ou projeto.
2. **Estado afetivo autoritativo.** O avatar não escreve nas seis dimensões afetivas nem gera `ImpulsoAfetivo`.
3. **Expressão derivada.** Toda expressão visível é calculada a partir de estado já interpretado.
4. **Separação entre sentir e demonstrar.** Uma emoção interna moderada não exige expressão dramática.
5. **Transição contínua.** Mudanças visuais pequenas são interpoladas; eventos críticos podem interromper animações de baixa prioridade.
6. **Histerese.** Oscilações breves de telemetria ou pequenos impulsos não devem produzir flicker emocional.
7. **Falha segura.** Falha do avatar não derruba Atlas Core, Observation Runtime, voz, estado técnico ou estado afetivo.
8. **Cliente leve.** A renderização ocorre no navegador; o Pentium envia somente estado derivado necessário.
9. **Privacidade por isolamento.** O avatar não recebe áudio bruto, gravações, perfil vocal, credenciais ou dados biométricos.
10. **Identidade visual estável.** Emoções mudam expressão e postura, não a identidade facial do Atlas.
11. **LLM fora do compositor.** Escolha de expressão, gesto, foco e transição não depende de LLM.
12. **Renderer substituível.** O contrato de estado não depende da implementação interna do SVG.

## Identidade visual canônica

A versão 1 deve preservar:

- estilo visual anime;
- cabelo longo violeta/roxo-escuro;
- olhos verdes expressivos;
- aparência acolhedora, calma e inteligente;
- roupa principal azul-escura sobre camisa branca;
- expressão-base receptiva, com leve sorriso;
- presença visual de companheiro tecnológico, não de painel corporativo;
- proporções e traços consistentes entre estados.

A aparência-base é invariável em função da emoção. O sistema pode alterar expressão facial, direção do olhar, postura, pequenos gestos, velocidade de movimento, intensidade de animação e efeitos sutis, mas não deve transformar o Atlas em outra pessoa.

A identidade visual possui versionamento próprio:

```text
versao_avatar = 1
identidade_visual = atlas
renderer = svg_camadas
```

Esse versionamento é independente do esquema do Motor de Estado Afetivo.

## Renderer 2D aprovado para v1

A primeira implementação usa **SVG por camadas**, renderizado no navegador. Não será usado vídeo pré-renderizado, modelo 3D ou rig dependente de GPU.

Estrutura mínima:

```text
AtlasBase
├── corpo
├── cabelo
├── olhos
├── sobrancelhas
├── boca
├── cabeca
├── bracos_gestos
└── efeitos_sutis
```

As camadas podem usar transformações SVG/CSS para rotação leve da cabeça, deslocamento de olhos, alteração de boca/sobrancelha, postura e pequenos gestos. O renderer deve aceitar `EstadoVisualAtlas` como entrada e não consultar o Motor de Estado Afetivo diretamente.

A imagem de referência aprovada não precisa ser carregada pelo runtime para o contrato funcionar. Os assets versionados da implementação devem respeitar as características canônicas desta especificação.

## Contrato `EstadoVisualAtlas`

O avatar consome um estado derivado com os seguintes campos conceituais:

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

### Regras de domínio

- `intensidade_expressao`: `0.0..1.0`;
- `velocidade_movimento`: `0.0..1.0`;
- `intensidade_movimento`: `0.0..1.0`;
- `foco_visual` referencia uma entidade ou contexto já resolvido, nunca telemetria bruta;
- `duvida_identidade` representa somente estado de comunicação recebido da camada de identidade;
- `transicao_ms` deve ficar entre `120` e `1500` ms;
- valor fora de faixa é limitado ou rejeitado pelo contrato conforme a natureza do campo, sem quebrar a página;
- ausência de foco válido resulta em foco neutro, não em erro fatal.

O estado visual não é persistido como fonte de verdade. Após reinício, ele é reconstruído a partir do estado afetivo atual, foco atual e contexto presente.

## Política visual inicial

A política v1 usa os seguintes valores iniciais versionados:

```text
transicao_padrao_ms = 400
transicao_critica_ms = 160
permanencia_minima_arquetipo_ms = 1200
intervalo_gesto_ocioso_min_ms = 4000
intervalo_gesto_ocioso_max_ms = 12000
```

Regras:

- evento crítico pode ignorar `permanencia_minima_arquetipo_ms`;
- recuperação não ignora a permanência mínima, salvo se encerrar um estado crítico;
- gestos ociosos seguem sequência determinística e limitada dentro do intervalo configurado;
- mudança de foco pode atualizar o olhar imediatamente sem exigir troca de arquétipo;
- os valores são configuração versionada, não constantes espalhadas no renderer.

## Modos comportamentais

### `OCIOSO`

Usado quando não existe interação ativa nem evento que exija foco imediato.

Comportamento:

- postura relaxada;
- respiração/animação sutil;
- pequenos movimentos naturais;
- exploração lenta do ambiente com o olhar;
- expressão coerente com o estado afetivo atual;
- baixa frequência de gestos para evitar ruído visual.

### `OBSERVANDO`

Usado quando uma entidade, projeto, serviço ou evento passa a ser o foco principal.

Comportamento:

- olhar direcionado ao foco;
- postura mais concentrada;
- redução de movimentos aleatórios;
- expressão coerente com relevância e estado afetivo;
- manutenção do foco enquanto a causa continuar relevante.

### `CONVERSANDO`

Usado durante interação com uma pessoa pela interface web ou futura camada de voz.

Comportamento:

- contato visual mais direto;
- pequenos gestos coerentes com a fala;
- sinal de escuta quando `ouvindo=true`;
- sinal de concentração quando `pensando=true`;
- lip-sync estilizado quando `falando=true`;
- reação visual consistente com o contexto afetivo.

O lip-sync v1 é estilizado e baseado em estados discretos de boca; não exige análise fonética avançada.

### `REAGINDO`

Usado para resposta transitória a evento relevante.

```text
evento relevante
→ reação curta
→ redirecionamento do olhar
→ ajuste de postura
→ expressão derivada
→ transição para OBSERVANDO ou CONVERSANDO
```

Reações são curtas e não bloqueiam a interface.

## Arquétipos visuais

Os arquétipos são rótulos derivados de expressão. Eles não são novas emoções do motor.

### `SERENO`

- sorriso leve;
- olhar suave;
- postura relaxada;
- movimentos lentos e estáveis.

### `ENGAJADO`

- olhar direto;
- postura aberta;
- maior presença corporal;
- pequenos gestos de acompanhamento.

### `CURIOSO`

- olhos mais atentos;
- leve inclinação da cabeça;
- exploração visual do foco;
- expressão interessada.

### `ATENTO`

- expressão neutra e focada;
- postura mais ereta;
- olhar direcionado;
- menor quantidade de gestos ociosos.

### `PREOCUPADO`

- sorriso ausente;
- tensão moderada em sobrancelhas e olhar;
- postura mais contida;
- foco reforçado na causa relevante.

### `SOB_PRESSAO`

- movimentos menores e mais rápidos;
- olhar concentrado;
- tensão claramente perceptível;
- redução de comportamento casual.

### `RECUPERANDO`

- diminuição gradual da tensão;
- desaceleração dos movimentos;
- retorno progressivo do sorriso;
- transição visual para estado compatível com a nova realidade.

## Composição afetiva

O arquétipo visual e sua intensidade são derivados da combinação das seis dimensões afetivas, foco e contexto recente:

```text
valencia
ativacao
estresse
confianca
engajamento
curiosidade
foco_atencao
evento_relevante
        ↓
CompositorVisualAfetivo
        ↓
EstadoVisualAtlas
```

Nenhuma dimensão isolada define a expressão. O compositor suporta estados mistos, como preocupação com curiosidade ou alívio após estresse.

Exemplo:

```text
estresse = 0.42
ativacao = 0.68
foco = core

→ expressao = ATENTO
→ intensidade_expressao = moderada
→ direcao_olhar = core
→ postura = concentrada
```

O sistema não converte automaticamente `estresse=0.42` em tristeza.

## Intensidade e transições

A intensidade varia continuamente entre `0.0` e `1.0` dentro de cada arquétipo.

```text
PREOCUPADO 0.2 → alteração discreta
PREOCUPADO 0.6 → expressão claramente séria
PREOCUPADO 0.9 → atenção intensa e pouca movimentação casual
```

Regras:

- mudança pequena: `transicao_padrao_ms`;
- mudança crítica: `transicao_critica_ms`;
- evento crítico pode interromper gesto ou animação de baixa prioridade;
- recuperação reduz tensão progressivamente, sem salto visual abrupto;
- troca normal de arquétipo exige permanência mínima configurada;
- mudança de intensidade dentro do mesmo arquétipo não reinicia a permanência mínima.

O compositor nunca representa pânico quando o estado técnico considera a situação normal.

## Foco e direção do olhar

O olhar é o principal canal visual de atenção.

```text
foco_atencao = L2jToren
→ olhar direcionado à representação do projeto

foco_atencao = Deraldo
→ contato visual com a interface de conversa

foco_atencao = firewall
→ foco visual no elemento de comunicação correspondente
```

Eventos com prioridade superior podem assumir o foco temporariamente. O avatar não escolhe essa prioridade sozinho; ele recebe o foco resolvido pela camada responsável.

## Gestos mínimos da versão 1

O catálogo inicial contém:

- leve inclinação de cabeça;
- olhar lateral;
- pequeno aceno;
- postura mais aberta;
- postura mais fechada;
- surpresa curta;
- relaxamento/alívio;
- gesto de escuta;
- gesto de dúvida.

Gestos são limitados em duração e frequência. Eles não competem continuamente com a informação principal da interface.

## Dúvida de identidade

Quando a camada de identidade informar estado duvidoso:

```text
identidade = DUVIDOSA
```

O avatar deve:

- mostrar expressão de incerteza;
- executar leve inclinação de cabeça ou gesto equivalente;
- assumir olhar investigativo;
- permitir que a camada sonora emita um som curto de dúvida;
- manter conversação não sensível possível;
- não representar reconhecimento confirmado.

O avatar não decide se a pessoa é Deraldo e não altera perfil vocal.

## Despertar inicial

No primeiro despertar verdadeiro:

```text
Pentium inicia
→ Atlas entra em DESPERTAR_INICIAL
→ avatar surge e abre os olhos gradualmente
→ executa pequena animação de orientação
→ camada sonora emite som canônico de despertar
→ Atlas começa a escutar
```

A sequência permite que Deraldo diga naturalmente:

> “Olá Atlas, eu sou Deraldo.”

A associação de identidade e a confirmação local pertencem à camada de identidade/voz, não ao avatar.

## Boot normal

Reinicializações posteriores usam uma versão curta e discreta do despertar. O boot normal não recria o ritual de primeiro despertar nem redefine identidade.

## Eventos consumidos pelo avatar

A camada visual pode receber eventos derivados equivalentes a:

- `AFETO_ATUALIZADO`;
- `FOCO_ALTERADO`;
- `INTERACAO_INICIADA`;
- `INTERACAO_ENCERRADA`;
- `IDENTIDADE_RECONHECIDA`;
- `IDENTIDADE_DUVIDOSA`;
- `ENTIDADE_RELEVANTE_ALTERADA`;
- `RECUPERACAO_DETECTADA`;
- `DESPERTAR_INICIAL`;
- `BOOT_NORMAL`.

Esses nomes representam contratos conceituais. A implementação deve alinhar os identificadores finais ao padrão vigente do repositório e manter novos contratos em português do Brasil, sem acentos em identificadores quando necessário.

## Persistência e retomada

`EstadoVisualAtlas` é efêmero. O sistema não persiste “último rosto”, “última pose” ou “último arquétipo” como verdade independente.

Na retomada:

1. o estado afetivo é restaurado pelos mecanismos próprios;
2. a realidade técnica atual é reconstruída;
3. foco e contexto atual são resolvidos;
4. `EstadoVisualAtlas` é recalculado;
5. o renderer inicia a animação correspondente.

Um snapshot antigo nunca mantém o Atlas preocupado se a realidade atual já está saudável.

## Falhas e fallback

Se o componente visual falhar:

- Atlas Core continua ativo;
- Observation Runtime continua ativo;
- Motor de Estado Afetivo continua ativo;
- voz futura continua independente;
- nenhuma ação operacional é perdida por depender do avatar.

Fallback mínimo:

- representação estática do Atlas ou ícone simples;
- texto curto de estado de comunicação;
- reconexão ao stream de estado visual;
- registro do erro sem reiniciar o núcleo afetivo.

Asset ausente não quebra toda a página. Falha em uma camada SVG usa a última composição válida ou o fallback estático.

## Privacidade e segurança

O avatar não recebe diretamente:

- áudio bruto;
- gravações de voz;
- embeddings ou perfil vocal;
- imagem de câmera;
- credenciais;
- tokens;
- comandos administrativos;
- shell;
- telemetria técnica bruta quando não necessária à apresentação.

A camada visual recebe somente dados derivados necessários para representação.

## Testabilidade

A implementação permite testes determinísticos do compositor e do contrato visual sem navegador real para toda a suíte. O renderer SVG possui testes próprios de estrutura e transformação, enquanto testes de integração web ficam na slice Interface Web Companion.

Casos mínimos:

- cada modo comportamental produz contrato válido;
- cada arquétipo aceita intensidade válida;
- intensidades e velocidades são limitadas a `0.0..1.0`;
- `transicao_ms` permanece entre `120` e `1500`;
- política visual carrega os valores versionados aprovados;
- histerese mantém arquétipo por pelo menos `1200` ms em transições normais;
- evento crítico pode ultrapassar a histerese;
- dúvida de identidade não vira reconhecimento;
- foco altera direção de olhar sem alterar estado técnico;
- recuperação reduz tensão gradualmente;
- restart recalcula expressão a partir do estado atual;
- asset ausente ativa fallback;
- entrada inválida não derruba o runtime;
- renderer recebe `EstadoVisualAtlas` sem consultar telemetria bruta;
- número de chamadas de LLM para escolher expressão é zero.

## Critérios de conclusão da versão 1

A implementação do Avatar v1 estará concluída quando houver evidência no HEAD exato de que:

- a identidade visual permanece reconhecível e consistente;
- o renderer SVG por camadas está implementado;
- os quatro modos comportamentais estão implementados;
- os sete arquétipos visuais estão implementados;
- intensidade contínua está integrada;
- foco visual e direção do olhar funcionam;
- animação ociosa existe e é limitada;
- gestos mínimos funcionam;
- reação a eventos relevantes funciona;
- dúvida de identidade possui sinal visual próprio;
- despertar inicial e boot normal são distintos;
- transições suaves e histerese evitam flicker;
- o estado visual deriva do estado afetivo real e do foco resolvido;
- falha do avatar não afeta o núcleo do Atlas;
- fallback visual funciona;
- testes do contrato, compositor e renderer estão GREEN;
- não existe dependência de LLM para decidir expressão;
- documentação e CI aplicáveis estão GREEN no mesmo SHA.

## Relação com as próximas slices

Esta especificação é a primeira das três slices aprovadas em sequência:

1. **Avatar v1** — esta especificação;
2. **Interface Web Companion** — presença do Atlas, conversa e visão integrada do homelab sem dashboard tradicional;
3. **Voz e Sons** — despertar sonoro, fala, escuta, identidade vocal, dúvida explícita e integração futura com LLM.

A Interface Web Companion deve consumir `EstadoVisualAtlas` sem duplicar o Motor de Estado Afetivo. A camada de Voz e Sons comunica estados de escuta, fala e dúvida ao avatar por contratos derivados, sem entregar áudio bruto à camada visual.
