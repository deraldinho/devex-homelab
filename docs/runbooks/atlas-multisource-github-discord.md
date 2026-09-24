# Atlas Multisource + GitHub + Discord

## Regra arquitetural

Atlas continua sendo o mini pet/IA emocional da infraestrutura. Nenhuma integração nova pode publicar respostas operacionais por fora do pipeline canônico:

`ObservationRuntime -> percepção -> impacto afetivo -> foco/emoção -> contexto cognitivo -> Hermes -> ActionPlan -> visual/chat`.

Pentium, Core, x99 e GitHub são sentidos do mesmo Atlas. Discord e dashboard são apenas canais do mesmo ciclo cognitivo.

## Fontes ativas

- `pentium.self`: coleta local bounded; `self_healthy` alimenta percepção afetiva.
- `managed.core`: READ via `ManagedReadService`; `channel_healthy` alimenta percepção afetiva.
- `managed.x99`: READ via `ManagedReadService`; `channel_healthy` alimenta percepção afetiva.
- `managed.x99.l2j`: Sondas determinísticas TCP e flash query SSH no Windows x99 monitorando portas e containers do L2jToren.
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
ATLAS_DISCORD_CHANNEL_IDS=<canal-chat>,<canal-alertas>,<canal-memorias>,<canal-logs>
ATLAS_DISCORD_USER_IDS=*
ATLAS_DISCORD_ADMIN_USER_IDS=<user-id-do-operador>
ATLAS_DISCORD_ALERT_CHANNEL_ID=<canal-alertas>
ATLAS_DISCORD_MEMORY_CHANNEL_ID=<canal-memorias>
ATLAS_DISCORD_NOTES_CHANNEL_ID=<canal-anotacoes-logs>
ATLAS_DISCORD_CONSOLE_CHANNEL_ID=<canal-console>
```

Canais especializados configurados para o servidor DevExMachina (`1409654606849638440`):
- `ATLAS_DISCORD_ALERT_CHANNEL_ID`: `#🤖│watchdog` (`1476441917020700773`)
- `ATLAS_DISCORD_MEMORY_CHANNEL_ID`: `#📝│audit-log` (`1473703460385063065`) — Memórias episódicas e reflexões da Atlas
- `ATLAS_DISCORD_NOTES_CHANNEL_ID`: `#📄│logs` (`1476390422506111127`) — Anotações do workspace e diário operacional
- `ATLAS_DISCORD_CONSOLE_CHANNEL_ID`: `#⚙️│bot-console` (`1473703295611568213`) — Console e interações diretas

O canal de alertas precisa fazer parte de `ATLAS_DISCORD_CHANNEL_IDS`. O bot precisa ter o Message Content Intent habilitado no Discord Developer Portal.

## Controle Operacional de Canais e Mensagens

O bot possui permissões de Administrador e aceita comandos diretos do operador autorizado (`ATLAS_DISCORD_USER_IDS`):

### Gestão de Canais
- `!canal criar <nome> [topico]`: Cria um canal de texto no servidor.
- `!canal renomear <#canal|id|nome> <novo_nome>`: Renomeia um canal existente.
- `!canal topico <#canal|id|nome> <novo_topico>`: Altera o tópico/descrição.
- `!canal excluir <#canal|id|nome>`: Exclui o canal (proteção automática impede excluir canais vitais como `#watchdog`, `#audit-log`, `#bot-console`, `#logs`).
- `!canal listar`: Lista todos os canais de texto do servidor com seus IDs.

### Gestão de Mensagens
- `!msg excluir [id_msg]`: Exclui a mensagem (ou responda a ela com o comando).
- `!msg editar <id_msg> <novo_conteudo>`: Edita mensagens enviadas pelo bot.
- `!msg fixar [id_msg]` / `!msg desfixar [id_msg]`: Fixa ou desafixa mensagens no canal.
- `!limpar [quantidade]`: Expurga mensagens recentes do canal (padrão: 10, máximo: 100).
- `!ajuda`: Exibe o menu interativo com todos os comandos.

## Capabilities Acionadas Autonomamente pelo Hermes

O cérebro cognitivo Hermes 3 pode acionar intenções estruturadas allowlisted diretamente em resposta aos estímulos e diálogos no Discord:

| Capability | Parâmetros | Descrição |
|---|---|---|
| `get_cluster_vitals` | `{}` | Diagnóstico proprioceptivo consolidado dos 3 nós (`pentium`, `core`, `x99`). |
| `git_get_status` | `{"repo": "..."}` | Status da árvore de trabalho e branch de repositórios locais. |
| `git_recent_commits` | `{"repo": "...", "limit": 5}` | Lista os últimos commits para entender o histórico recente. |
| `l2j_get_status` | `{"host": "..."}` | Status consolidado do L2jToren (portas + containers + heap). |
| `l2j_docker_stats` | `{"host": "..."}` | Inspeção imediata dos containers Docker no x99. |
| `l2j_check_jvm` | `{"host": "..."}` | Telemetria do Heap da JVM e threads via Prometheus. |
| `l2j_probe_ports` | `{"host": "..."}` | Varredura das 6 portas de rede do ecossistema. |
| `discord_post_note` | `{"title": "...", "content": "..."}` | Registra uma nota no canal `#📄│logs`. |
| `discord_create_channel` | `{"name": "...", "topic": "..."}` | Cria um canal operacional no servidor. |

Após configurar e validar:

```bash
chmod 600 ~/pentium-agent/atlas/runtime/discord.env
systemctl --user daemon-reload
systemctl --user enable --now atlas-discord.service
systemctl --user status atlas-discord.service --no-pager
```

Sem token, allowlists ou runtime `discord.py`, o gateway falha fechado; `atlas-observation`, `atlas-cognitive`, dashboard, voz e comportamento do pet continuam independentes.
