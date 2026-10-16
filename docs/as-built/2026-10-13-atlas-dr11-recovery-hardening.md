# Atlas / DevEx — CP-DR11 segurança de restauração e empacotamento (2026-10-13)

## Resultado: GREEN de engenharia em isolamento; HOLD para proteção real
Esta execução ocorreu na branch original do x99 `atlas/v0.4.0-proprioception-autonomy` e consultou `core`/`pentium` por SSH autenticado sobre Tailscale. **Nenhum backup dos dados reais, instalação em hosts, timer, serviço, reinício, push, commit ou implantação foi realizado.**

### DR real — inventário físico autenticado
- `core` e `pentium`: comando `restic` **ausente** no host; `homelab-backup.timer` **não encontrado** (system/user); `/etc/homelab/backup.env` e `/etc/homelab/secrets/restic.key` **não encontrados**.
- Diretório/repositório Restic real e arquivo `backup_status.json` **não comprovados**.
- Pentium: user services `atlas-cognitive`, `atlas-observation`, `atlas-dashboard`, `atlas-discord` ativos em verificação anterior; nenhum alterado.
- P0 Issue #11 não certificada; API de GitHub para issue privada retornou 404 e não fornece prova de restauração. `CP-H12` permanece sem certificação integral de release/rollback.

### Implementado no projeto — TDD
1. `infrastructure/backup/restic-verify.sh`: substituído o `rm -rf "$TARGET_DIR"` direto (perigoso) por **diretório-filha único e privado** sob parent já existente, checagem de root/symlink, limpeza apenas da filha pelo trap. Lista snapshots por tag de nó, seleciona o último **por timestamp** com ID hex validado; rejeita JSON/snapshot/restauração inválidos, restaurações vazias e symlinks; testa SQLite com `PRAGMA integrity_check`, e nega se SQLite CLI ausente quando necessário. Só imprime `DEVEX_HOMELAB_BACKUP_VERIFY_PASS` após validação.
2. `infrastructure/backup/tests/test_restic_verify_safe.py`: 13 testes sintéticos de falhas/sucesso, dados/credenciais fictícios, preservação de arquivos existentes e negação de caminhos perigosos.
3. `tools/atlas-dr11-test-core.ps1`: injeta apenas esses arquivos em contêiner Docker descartável no core, sem redes/mounts/segredos; **13 testes passaram**.
4. `tools/atlas-dr11-real-restic-core.ps1`: constrói imagem efêmera a partir de runner já cacheado e Restic real 0.17.3; `restic init`, snapshot de texto+SQLite fictícios, restore pelo script revisado, integrity_check SQLite e sentinel preservado. **`REAL_RESTIC_ENGINE_RESTORE_PASS`**, contêiner exit 0. `production_backup_restored=false`.
5. Dockerfile para backup pinado em `restic/restic:0.17.3@sha256:8f5a62b422a2cb1277ea0dd6e826fe1acf649e5b9f02d60e5268d5fd1976255a`, `python3`, `sqlite`, `curl`, `ca-certificates`, `openssh-client`; inclui `restic-backup.sh`, `restic-verify.sh`, `github-sync.sh`; executa sem root.
6. `infrastructure/backup/compose.yaml`: substituiu uso direto da imagem upstream, que não tinha Python/SQLite nem scripts, por build declarativo, flags default-deny para configuração de source/repo/status/password, volume fonte e chave `:ro`, read_only, cap_drop=ALL, no-new-privileges e sem portas.
7. `tools/atlas-dr11-build-core.ps1`: empacotou fontes locais e compilou **somente imagem de teste descartável** no core (sem credenciais de produção); runtime da imagem confirmou `restic`, `python3`, `sqlite3`, `curl` e os três scripts: **`RESTIC_BACKUP_PACKAGING_PASS`**. Docker Compose `config --quiet` com paths sintéticos validado, sem `up`.

### Evidências locais
- `.atlas/opencode/tmp/cp-dr11-verifier-tests.log`: 13/13 testes sintéticos Linux PASS.
- `.atlas/opencode/tmp/cp-dr11-real-restic-engine.log`: snapshot+restauração reais do motor sobre **dados fictícios**, PASS.
- `.atlas/opencode/tmp/cp-dr11-packaging-build.log`: imagem de backup build + ferramentas presentes, PASS.
- `py -m pytest --import-mode=importlib infrastructure/backup/tests -q`: 11 passed, 13 skipped no Windows (13 testes POSIX rodados separadamente no core).
- `git diff --check`: sem inconsistências de whitespace.
- OpenCode recebeu `20261013T040959Z-c653cd9a`, porém travou após leitura e foi interrompido (`agent_interrupted`, sem report). A implementação e os testes concluídos foram executados pelo orquestrador, não creditados ao OpenCode.

### Pendências bloqueantes antes da Issue #11 virar GREEN
- Configurar armazenamento durável, chaves criptográficas via canal seguro, rotas de backup cruzadas, restores reais de **Pentium e Core** e verificações de integridade, sem afetar serviços. Não gerar/distribuir segredos fictícios em produção.
- Revisar `restic-backup.sh`: executa `unlock` automaticamente e trata qualquer falha em `snapshots` como repositório não inicializado; ainda permite fallback de SQLite transacional para cópia comum. Esses comportamentos são perigosos e **devem receber checkpoint separado com TDD antes de ativar timers**.
- Revisar offsite `github-sync.sh`, credenciais/retention, status/heartbeat, permissões de UID 65534 nos volumes e CP-H12. A imagem de teste e o repositório sintético não substituem essas provas.
- `agency_specialists.enabled` permanece `false`; `task_specialist_review` continua default-denied. Não executar subagentes reais ainda.

**Decisão:** manter promoção em HOLD até backup real restaurável e rollbacks certificados. Nenhum serviço de produção foi alterado.
