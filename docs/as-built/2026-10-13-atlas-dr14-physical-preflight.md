# CP-DR14 — Inventário físico de prontidão de backup
**Data:** 2026-10-13 · **Estado:** GREEN para implementação/testes do diagnóstico; **BLOCKED / P0** para backup físico e certificação de restauração.

## Escopo e procedimento
Foi integrado `infrastructure/backup/dr14_preflight.py` no repositório original `C:\Users\deral\DevEx-HomeLab` e criado `tools/atlas-dr14-inventory.ps1`. A orquestração usa SSH batch autenticado da x99 para Core e Pentium e envia o código Python por stdin (base64). Não escreve arquivos nos servidores. Os dois relatórios locais ficam em `.atlas/opencode/tmp/cp-dr14-{core,pentium}-preflight.json`.

O script somente consulta metadata de configuração e credenciais (sem ler os conteúdos), executa `command -v` e `systemctl is-enabled/is-active`, e marca explicitamente `restoration_certification=NOT_TESTED` e `offsite_certification=NOT_TESTED`. Ele **não** executa backup, init, unlock, snapshots, restore, alterações de serviço, sudo, apt ou leitura de dados reais. A saída não contém conteúdo de secrets.

## Constatações observadas por SSH nos hosts reais

| Gate | Core | Pentium |
|---|---|---|
| Conexão SSH batch, host key rígida | PASS via `core-auto` | PASS via chave x99 `id_ed25519` e IP tailnet existente |
| Python 3 | PASS | PASS |
| Cliente Tailscale | PASS | PASS |
| Binário Restic no host | **PRESENTE no escopo usuário** (`~/.local/bin/restic`, versão 0.18.1); não em `/usr/bin` | **AUSENTE** |
| Binário sqlite3 no host | **PRESENTE no escopo usuário** (`~/.local/bin/sqlite3`, versão 3.46.1); não em `/usr/bin` | PASS |
| `/etc/homelab/backup.env` regular e owner-only | **AUSENTE** | **AUSENTE** |
| `/etc/homelab/secrets/restic.key` regular e owner-only | **AUSENTE** | **AUSENTE** |
| `homelab-backup.timer` habilitado e ativo | **NÃO** | **NÃO** |
| Serviço `homelab-backup.service` encontrado em `systemctl cat` | **NÃO** | **NÃO** |
| `/var/backups/homelab` ou `/opt/homelab/backup` comprovados | Não detectados nesta observação | Não confirmados nesta observação |
| Sudo batch sem interação disponível | **NÃO** | **NÃO** |
| Snapshot real + restauração + offsite | **NÃO TESTADOS** | **NÃO TESTADOS** |

Resultados localmente gravados no x99:
- `.atlas/opencode/tmp/cp-dr14-core-preflight.json`;
- `.atlas/opencode/tmp/cp-dr14-pentium-preflight.json`.

**Interpretação:** nenhuma certificação de proteção dos dados foi obtida. A existência de um Restic Docker image usado nos testes de DR-13 não significa que `restic` esteja instalado no host ou que o backup de produção esteja operacional.

## Mudanças no código, sem rollout
1. `infrastructure/backup/dr14_preflight.py`: nova leitura de prerequisites, enum dos blockers e isolamento de conteúdo de credenciais.
2. `infrastructure/backup/tests/test_dr14_preflight.py`: TDD sintético para arquivos secretos não lidos, segurança de symlink/permissões, argumentos, falta de binários, retorno não-certificado e integridade de relatório.
3. `tools/atlas-dr14-inventory.ps1`: runner de inventário remoto sem arquivo ou sudo nos nós.
4. `infrastructure/backup/tests/test_dr14_deployment_contract.py`: testes de contrato antes da configuração física.
5. `infrastructure/backup/systemd/homelab-backup.service`: o `EnvironmentFile` deixa de ser opcional; se o arquivo obrigatório faltar, a futura unidade falhará fechada.
6. `infrastructure/backup/backup.env.example`: template somente documental com placeholders impeditivos; sem password/token.
7. `docs/status/atlas-checkpoints.md` e `docs/runbooks/disaster-recovery.md`: status físico e pendências reconciliados.

## Testes
- `py -m pytest -q infrastructure/backup/tests/test_dr14_preflight.py infrastructure/backup/tests/test_dr14_deployment_contract.py` → **12 passed, 1 skipped** (symlink sem privilégios no Windows); log `.atlas/opencode/tmp/cp-dr14-focused-tests.log`.
- `py -m pytest --import-mode=importlib infrastructure/pentium/atlas/tests infrastructure/pentium/agent/tests infrastructure/backup/tests -q` → **1149 passed, 25 skipped, 53 subtests passed** em 26.33s **após a integração final** dos testes estáticos DR-14. Log: `.atlas/opencode/tmp/cp-dr14-full-regression.log`.
- `git diff --check` → exit 0.
- Host físico: dois relatórios JSON com `status=BLOCKED` e razões explícitas.

## Gates necessários para DR real
1. Definir fonte aprovada por nó e escopo de dados protegidos; documentar exclusões, volumes, banco SQLite, retention e janela de consistência. **Não** alterar os serviços operacionais.
2. Escolher destino durável e offsite seguro por nó. Validar caminho do repositório no host versus `/repo` da imagem Docker — a configuração atual não prova essa correspondência.
3. Provisionar Restic, SQLite (Core), fontes/status/staging, chave criptográfica e `backup.env` de modo seguro via acesso administrativo e change record. Não copiar env com segredo para Git/ChatGPT. `sudo -n` não estava disponível nos hosts.
4. Testar primeiro um backup de uma fonte real aprovada, pequeno e controlado, sem rodar `forget --prune` em repositório desconhecido. Exigir restore isolado, conteúdo correto, hashes/SQLite integrity e exclusão de symlinks.
5. Apenas depois de comprovar a recuperação, habilitar timer sob janela controlada, monitorar primeira execução e restaurar de forma periódica.
6. Certificar CP-H12 depois da DR física; manter Agency AA7 e self-healing automáticos em HOLD.

**NÃO executados:** instalação de packages, criação de chaves, cópia de dados reais, ativação de timers, alteração de ambientes de serviço, mudança de permissões live, restart, branch, worktree, commit ou push.


## Incremento DR-14 / instalação no Core — 2026-10-13

A pedido do operador, foram instalados **somente no escopo do usuário** `deraldinho` do Core os binários oficiais da distribuição Ubuntu 26.04.1, extraídos de pacotes autenticados via apt:
- `/home/deraldinho/.local/bin/restic` — `restic 0.18.1`, Linux amd64.
- `/home/deraldinho/.local/bin/sqlite3` — `3.46.1`.

Acesso realizado por SSH `core-auto`; `apt-get download` + `dpkg-deb -x` + cópia atômica dos executáveis, sem `sudo`, sem `dpkg -i`, sem modificar `/usr/bin` ou serviços. A pasta temporária foi limpa. O teste remoto de ambas as versões retornou `CORE_USER_BIN_SMOKE_PASS`. Registro: `.atlas/opencode/tmp/cp-dr14-core-user-install.log`.

**Atenção ao PATH:** sessões SSH não interativas não incluem `~/.local/bin` automaticamente no Core. O executor de diagnóstico `tools/atlas-dr14-inventory.ps1` passou a incluir explicitamente esse caminho no processo SSH. Um futuro serviço `systemd` de sistema ou contêiner Docker **não** possui acesso automático aos binários do usuário; precisará de um contrato próprio de runtime e privilégio. Portanto esta instalação não representa implantação operacional do backup.

Novo preflight autenticado: Core bloqueado apenas por `backup_environment_missing_or_permissions`, `credential_reference_missing_or_permissions`, `backup_timer_not_enabled` e `backup_timer_not_active`. Pentium permanece sem Restic, env, credencial e timer.

**Não foram criados repositórios Restic reais, chaves, backups de produção, restaurações, timer ou alterações de serviços.** A certificação de DR continua P0 BLOCKED, assim como CP-H12 e AA7.


## Retificação do alvo da instalação — 2026-10-13

O operador esclareceu que **o destino correto é o Pentium**, onde reside o runtime Atlas. O Core havia recebido por engano executáveis em `~/.local/bin`; ambos os binários de usuário foram removidos após validar suas versões. Evidência SSH: `CORE_USER_BINARIES_ROLLED_BACK`. Nenhum pacote de sistema ou serviço Core foi modificado.

No Pentium, o binário oficial Ubuntu de **Restic 0.18.1** foi extraído e instalado como `/home/deraldinho/.local/bin/restic`, sem `sudo`. O `sqlite3` **já existia** em `/usr/bin/sqlite3` versão **3.46.1** e não foi reinstalado. Evidência: `.atlas/opencode/tmp/cp-dr14-pentium-user-install.log` com `PENTIUM_RESTIC_USER_INSTALL_PASS`.

O inventário renovado aponta:
- **Pentium:** Restic, sqlite3, Python e Tailscale presentes; permanecem ausentes a configuração, a credencial e o timer de backup.
- **Core:** binários de usuário removidos, como solicitado pela retificação; permanece sem Restic/sqlite3 host e sem configuração/timer.

**Sem ativação de backup, instalação systemd, alteração de serviços Atlas ou acesso a credenciais.** O uso futuro pelo systemd exige PATH explícito para `~/.local/bin` ou artefato de runtime aprovado. A certificação física do DR permanece BLOCKED.
