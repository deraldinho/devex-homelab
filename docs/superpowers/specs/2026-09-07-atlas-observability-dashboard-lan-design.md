# Atlas Observability Dashboard — LAN Design

## Objetivo

Criar uma interface web read-only para observar o Atlas executando no Pentium a partir do x99 pela LAN cabeada.

O dashboard deve explicar o estado atual do Atlas sem oferecer shell, SSH, CONTROL, restart, mutação de configuração ou qualquer endpoint de escrita.

## Rede autoritativa

- Pentium LAN: `enp4s0`, `192.168.88.3/24`
- x99 LAN: `Ethernet 2`, `192.168.88.4/24`
- Bind do dashboard: `192.168.88.3:8765`
- URL esperada no x99: `http://192.168.88.3:8765`
- Proibido bind em `0.0.0.0`.

A interface Wi-Fi `192.168.1.105` e Tailscale não são o caminho primário deste dashboard.
## Arquitetura

`atlas-dashboard.service` roda como serviço systemd de usuário no Pentium e expõe uma aplicação HTTP mínima em Python stdlib.

Fontes permitidas:

- `~/pentium-agent/data/health/latest.json`
- status systemd de serviços Atlas/Pentium
- `/proc` e `/sys` para CPU, memória, swap, uptime e temperatura quando disponível
- `/proc/asound` e `arecord -l` para inventário de áudio
- configuração Atlas sanitizada
- marker de SHA implantado
- journal do `atlas-voice.service` reduzido a markers técnicos permitidos

Nenhuma fonte deve exigir privilégio root ou escrita no sistema.
## API read-only

Endpoints permitidos:

- `GET /` — dashboard HTML
- `GET /api/status` — snapshot consolidado do estado atual
- `GET /api/events` — últimos eventos técnicos sanitizados
- `GET /healthz` — saúde do próprio dashboard

Qualquer método diferente de GET deve responder `405 Method Not Allowed`.

Não existem endpoints de restart, enable/disable, shell, SSH, CONTROL, alteração de configuração, upload ou execução arbitrária.

Respostas JSON usam tamanho limitado e timeout curto para cada coletor.
## Modelo de estado

O `/api/status` deve expor grupos estáveis:

- `atlas`: SHA implantado, estado global, uptime e último problema técnico
- `services`: agent, heartbeat, voice e dashboard
- `voice`: paused/listening/processing/speaking/degraded, último reason e disponibilidade de Whisper/Qwen/TTS
- `audio`: dispositivos ALSA detectados e estado diagnóstico agregado
- `anc`: off/calibrating/ready/active/degraded, principal, referência e motivo de bloqueio
- `system`: CPU, memória, swap, disco e temperatura quando disponível
- `network`: LAN, Wi-Fi e Tailscale observados sem expor credenciais

Campos ausentes devem ser `null`/`unknown`, nunca inventados.
## UI

Dashboard dark, responsivo e sem dependências externas obrigatórias.

Blocos principais:

- resumo Atlas
- pipeline `MIC → ANC → VAD → Whisper → Wake → Qwen → TTS`
- serviços
- áudio/microfones
- ANC
- CPU/RAM/swap/disco/rede
- timeline técnica

Atualização automática a cada 2 segundos via `fetch()`; falha de uma fonte deve degradar apenas o card afetado.

Estados visuais: `GREEN`, `YELLOW`, `RED`, `PAUSED` e `UNKNOWN`, sempre acompanhados de texto para não depender só de cor.
## Privacidade e segurança

- Não persistir áudio bruto.
- Não exibir nem armazenar transcrições de fala.
- Journal só pode contribuir com markers técnicos previamente permitidos.
- Configurações retornadas pela API devem ser sanitizadas e sem segredos.
- Nada do dashboard concede autorização de CONTROL.
- O servidor não importa nem instancia `ManagedControlService`.
- Sem templates executáveis, eval, subprocess arbitrário ou shell recebido por HTTP.
- Limites de payload e headers devem ser pequenos e fixos.

A LAN é tratada como rede de confiança operacional, mas o serviço continua read-only por design.
## Serviço e instalação

Adicionar:

- `atlas_dashboard.py` — servidor HTTP e roteamento GET-only
- `dashboard_collectors.py` — coleta bounded e sanitização
- `dashboard.html` — UI estática
- `atlas-dashboard.service` — systemd user service
- configuração do dashboard com bind `192.168.88.3` e porta `8765`

O instalador deve copiar, `py_compile`, instalar a unit, fazer `daemon-reload` e habilitar o serviço sem alterar `atlas-voice.service`.

A voz permanece pausada até decisão explícita posterior.
## Definition of Done

- testes unitários dos coletores e sanitização GREEN
- testes HTTP provam somente GET e `405` para escrita
- teste prova ausência de CONTROL/SSH dispatcher
- bind efetivo somente em `192.168.88.3:8765`
- x99 acessa `http://192.168.88.3:8765` pela LAN
- `/api/status`, `/api/events` e `/healthz` respondem bounded
- UI atualiza sem reload manual
- voice continua `disabled/inactive`
- regressão Atlas GREEN no SHA exato
- CI do SHA exato GREEN
- deploy/checksum físico no Pentium
- checkpoint na PR correspondente
