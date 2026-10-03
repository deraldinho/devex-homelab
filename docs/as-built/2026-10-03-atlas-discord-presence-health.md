# Atlas Discord Presence Health — 2026-10-03

## Sintoma
O Discord exibia `Atlas bot — Offline` apesar de `atlas-discord.service` permanecer `active (running)` e os serviços cognitive/observation continuarem saudáveis.

## Evidência e causa
- O processo Discord estava vivo e mantinha conexões TCP/443 estabelecidas com a infraestrutura Discord.
- O gateway não publicava presença `online` explicitamente.
- Não havia telemetria para `on_ready`, `on_disconnect` ou `on_resumed`, portanto `systemctl active` não distinguia processo vivo de sessão Discord conectada.
- O screenshot do usuário mostrou mensagens recentes do bot e, posteriormente, presença Offline, compatível com uma janela de desconexão/reconexão sem observabilidade.

## Alteração
- `DiscordGatewayHealthStore` persiste estado de sessão atomicamente em `runtime/discord-gateway-health.json`.
- `on_ready` e `on_resumed` publicam presença Discord `online` explicitamente.
- `on_disconnect` registra estado `disconnected`.
- Eventos READY/DISCONNECTED/RESUMED passam a aparecer no journal.
- Nenhuma lógica cognitiva, de memória, observação ou autorização foi removida.

## Verificação local
- RED confirmado: 2 testes falharam antes da implementação.
- Focado: `2 passed` em `test_discord_presence_health.py`.
- Regressão Discord: `22 passed` em `test_discord_gateway.py`.
- Atlas completo: `898 passed, 3 skipped, 38 subtests passed`.
