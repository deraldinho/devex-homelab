# Atlas Multisource + GitHub + Discord

## Regra arquitetural

Atlas continua sendo o mini pet/IA emocional da infraestrutura. Nenhuma integração nova pode publicar respostas operacionais por fora do pipeline canônico:

`ObservationRuntime -> percepção -> impacto afetivo -> foco/emoção -> contexto cognitivo -> Hermes -> ActionPlan -> visual/chat`.

Pentium, Core, x99 e GitHub são sentidos do mesmo Atlas. Discord e dashboard são apenas canais do mesmo ciclo cognitivo.

## Fontes ativas

- `pentium.self`: coleta local bounded; `self_healthy` alimenta percepção afetiva.
- `managed.core`: READ via `ManagedReadService`; `channel_healthy` alimenta percepção afetiva.
- `managed.x99`: READ via `ManagedReadService`; `channel_healthy` alimenta percepção afetiva.
- `github.deraldinho.devex-homelab`: PR/Issue/Actions reduzidos via `gh api`.
- `github.deraldinho.L2jToren`: PR/Issue/Actions reduzidos via `gh api`.
- `wifi.presence`: permanece observacional/diagnóstico e não altera emoção diretamente.

## GitHub READ-only

A autenticação fica fora do Atlas. O runtime executa `gh api` com argumentos fixos e `shell=False`; portanto o Pentium precisa ter GitHub CLI autenticado para os repositórios permitidos.

Verificação operacional:

```bash
gh auth status
gh api /repos/deraldinho/devex-homelab/pulls?state=open\&per_page=1
gh api /repos/deraldinho/L2jToren/actions/runs?per_page=1
```

Não colocar PAT, header Authorization, logs brutos ou diffs em `config_github.json`, Stimulus ou journals.

## Preparar Discord

O instalador principal apenas copia o gateway e a unit. Ele não instala dependências de rede nem habilita o serviço Discord automaticamente.

```bash
~/pentium-agent/atlas/prepare-discord-atlas.sh
mkdir -p ~/pentium-agent/atlas/runtime
chmod 700 ~/pentium-agent/atlas/runtime
```

Crie `~/pentium-agent/atlas/runtime/discord.env` localmente, com permissão `0600`, contendo somente as credenciais/IDs do ambiente:

```text
ATLAS_DISCORD_BOT_TOKEN=<token-local>
ATLAS_DISCORD_GUILD_IDS=<guild-id>
ATLAS_DISCORD_CHANNEL_IDS=<canal-chat>,<canal-alertas>
ATLAS_DISCORD_USER_IDS=<user-id-autorizado>
ATLAS_DISCORD_ALERT_CHANNEL_ID=<canal-alertas>
```

O canal de alertas precisa fazer parte de `ATLAS_DISCORD_CHANNEL_IDS`. O bot precisa ter o Message Content Intent habilitado no Discord Developer Portal.

Após configurar e validar:

```bash
chmod 600 ~/pentium-agent/atlas/runtime/discord.env
systemctl --user daemon-reload
systemctl --user enable --now atlas-discord.service
systemctl --user status atlas-discord.service --no-pager
```

Sem token, allowlists ou runtime `discord.py`, o gateway falha fechado; `atlas-observation`, `atlas-cognitive`, dashboard, voz e comportamento do pet continuam independentes.
