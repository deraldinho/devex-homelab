# Atlas Local Intelligence — Design de Domínio

## 1. Papel no DevEx HomeLab

O **Atlas** é a camada local de percepção e interação do DevEx HomeLab. Ele roda no `pentium` (`homelab.control`) e transforma observed state técnico em um estado global compreensível, reações sonoras e, em fases posteriores, interação por voz e linguagem natural.

O Atlas não substitui o Pentium Agent, o heartbeat, o Tailscale, o MikroTik nem os contratos de observabilidade existentes. Ele **consome** esses contratos e adiciona interpretação e interação acima deles.

## 2. Princípios

1. **Estado técnico é determinístico.** Uma LLM nunca decide se um nó está saudável, crítico ou autorizado a executar uma ação.
2. **Sem shell arbitrário.** A camada de linguagem produz intents estruturadas; somente o Policy/Action Engine pode resolver intents para ações allowlisted.
3. **Local-first.** Health, reactions e comandos básicos devem continuar funcionando sem Internet.
4. **Baixo orçamento de recursos.** O Pentium é Pentium Dual-Core T4300, 2C/2T, ~2,5 GiB RAM e ~2,8 GiB swap; a plataforma deve preservar o papel 24/7 de control plane.
5. **Expressão separada de severidade.** Um meme pode expressar emoção, mas nunca substitui um alerta técnico inequívoco.
6. **Sem repetição excessiva.** Cooldown, histerese, anti-repeat e quiet hours são parte do contrato, não detalhes cosméticos.

## 3. Componentes

```text
Observed State
  |-- management-network health
  |-- Pentium heartbeat
  |-- Pentium Agent actions
  |-- MikroTik / Internet / DNS adapters (futuro)
  |-- runners/jobs/services (futuro)
  v
Health Engine
  v
Global State + intensity + reasons
  |
  +--> Event Journal
  |
  +--> Reaction Engine
  |      |-- canonical sound category
  |      |-- optional meme category
  |      `-- cooldown/rarity/anti-repeat
  |              v
  |          Audio Engine
  |
  `--> Voice/LLM path (fases posteriores)
         microphone -> wake/VAD -> STT -> Qwen -> intent
                                      -> Policy -> allowlisted Action Engine
                                      -> TTS/response
```

## 4. Estados técnicos canônicos

- `healthy`: componentes obrigatórios saudáveis e sem pressão relevante;
- `active`: atividade presente sem pressão;
- `busy`: carga sustentada, porém dentro do orçamento;
- `degraded`: perda parcial de capacidade, latência/perda ou serviço não crítico degradado;
- `stressed`: recurso ou fila sob pressão sustentada, com risco de degradação;
- `critical`: indisponibilidade de componente obrigatório ou violação crítica;
- `recovered`: transição temporária após retorno de `degraded/stressed/critical` para condição saudável.

A severidade técnica não possui humor. A emoção/expressão é derivada separadamente.

## 5. Expressão e linguagem sonora

A comunicação normal usa uma linguagem sonora tecnológica própria. Cada categoria possui um **pool** de múltiplos sons, não um arquivo único.

Categorias iniciais de expressão:

- `calm`;
- `acknowledge`;
- `working`;
- `happy`;
- `concerned`;
- `annoyed`;
- `critical`;
- `relief`;
- `confused`;
- `victory`.

O Reaction Engine escolhe entre variantes com pesos, memória recente, raridade e cooldown. O conteúdo de áudio não faz parte do contrato técnico: mídia pode ser substituída sem mudar Health/Reaction.

Memes são uma segunda camada opcional. Em evento crítico, o som canônico de criticidade sempre precede ou substitui qualquer meme.

## 6. Intensidade

A intensidade é um inteiro de `0..4` calculado por regras determinísticas:

- `0`: neutro;
- `1`: reação discreta;
- `2`: perceptível;
- `3`: forte;
- `4`: crítico/especial.

Thresholds específicos ficam em configuração versionada e exigem duração mínima/histerese para evitar oscilações.

## 7. Mini LLM

O candidato inicial é `Qwen3-0.6B` em GGUF Q4 via `llama.cpp`, com contexto inicial limitado a 2048–4096 tokens. A promoção para serviço permanente depende de benchmark físico no Pentium: RAM, swap, CPU, tokens/s, latência e temperatura.

A LLM tem três funções permitidas:

1. interpretar linguagem humana para intent estruturada;
2. resumir observed state/event journal;
3. formular resposta humana.

Ela não recebe autoridade para avaliar gates técnicos, construir shell ou executar ações não allowlisted.

## 8. Voz

A trilha de voz será local-first:

`wake word -> VAD -> STT -> intent -> policy -> resposta -> TTS`.

A primeira promoção de voz será READ-only. Ações `CONTROL` só entram após allowlist explícita; ações `DESTRUCTIVE` exigem confirmação humana independente da LLM.

## 9. Modos de expressão

- `quiet`: apenas eventos importantes;
- `normal`: linguagem Atlas e memes raros;
- `expressive`: maior variedade e emoção;
- `chaos`: maior chance de reações especiais, sem alterar regras técnicas nem permissões.

## 10. Fases

1. Atlas State & Reaction Foundation;
2. Audio Engine e biblioteca local;
3. integração com MikroTik/Internet/DNS e runners;
4. benchmark e promoção da mini LLM;
5. voice input READ-only;
6. TTS;
7. Action Engine allowlisted;
8. journal consultável e resumo de histórico;
9. certificação física e as-built.

## 11. Limites da primeira slice

A primeira slice não instala LLM, STT, TTS, não baixa memes e não altera rede. Ela cria o modelo de estado global, o Reaction Engine, o journal e o contrato de biblioteca sonora, consumindo contratos já versionados sempre que possível.
