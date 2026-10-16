# CP-DR13 — Validação de restauração SQLite transacional no Restic
**Data:** 2026-10-13 · **Escopo:** `DevEx-HomeLab` original no x99; execução de integração somente em Core descartável.

## Resultado
**GREEN de engenharia e restauração sintética; HOLD para dados de produção.**

O CP-DR12 exclui os arquivos SQLite ativos do snapshot bruto e salva imagens ACID no diretório transitório `.restic-backup.XXXXXXXX/sqlite` com `manifest.json`. O DR11 verificava a restauração encontrando `*.sqlite`/`*.db` na árvore original, o que podia declarar PASS para um snapshot com **zero** bancos realmente reconstituídos.

O teste RED em `tools/atlas-dr13-real-restic-core.ps1` reproduziu isso com o motor Restic 0.17.3 real em dados fictícios: o verificador imprimiu `DEVEX_HOMELAB_BACKUP_VERIFY_PASS` e **0 bancos SQLite**, mas a verificação independente recusou o resultado por falta de banco restaurado. Log em `.atlas/opencode/tmp/cp-dr13-real-restic-engine.log` (registro de execução mais recente sobrescreve o primeiro).

## Implementação
- `infrastructure/backup/verify_sqlite_restore.py`: inspeciona a árvore privada restaurada; rejeita symlinks, arquivos não regulares, manifests duplicados, imagens órfãs, inclusão simultânea de banco vivo e imagem transacional, corrupção, paths não seguros e conflitos na restauração. Recompõe imagens por meio de `sqlite_snapshot.restore()` somente em uma subpasta própria do scratch; executa `PRAGMA integrity_check`.
- `infrastructure/backup/restic-verify.sh`: após a restauração Restic no filho `mktemp`, chama o verificador Python; qualquer erro aborta antes do marcador PASS. Mantém proteção do diretório-pai e o caminho legado.
- `infrastructure/backup/Dockerfile`: empacota ambos os helpers, sem alterar flags de produção.
- `infrastructure/backup/tests/test_verify_sqlite_restore.py`: casos sintéticos para imagens transacionais, integridade, traversal, manifest duplicado, symlink, combinação raw+stage, corrupção, preservação de arquivo, snapshot legado e texto sem banco.
- `infrastructure/backup/tests/test_restic_verify_safe.py`: fixture legado de SQLite atualizado para criar um banco SQLite válido em vez de texto `fake` declarado saudável.
- `tools/atlas-dr13-real-restic-core.ps1`: teste Restic real completo (criar SQLite + backup + restore + verificador), sem host mounts, credenciais reais, rede ou serviços; shim isolado de sqlite3 exige que o banco reconstituído contenha a linha `TRANSACTIONAL-OK`.
- `tools/atlas-dr11-test-core.ps1` e `tools/atlas-dr11-build-core.ps1`: pacotes de teste atualizados para incluir os novos helpers.
- `docs/status/atlas-checkpoints.md`: entrega local e bloqueio físico registrados separadamente.

## Evidência
- `py -m pytest infrastructure/backup/tests/test_verify_sqlite_restore.py -q`: **10 passed, 1 skipped** (symlink sem privilégios no Windows).
- `tools/atlas-dr11-test-core.ps1`: **13 testes POSIX PASS** em Core descartável com fixtures sintéticas e auxílio do verificador.
- `tools/atlas-dr13-real-restic-core.ps1`: `DR13_SQLITE_TRANSACTIONAL_PASS count=1`, `DEVEX_HOMELAB_BACKUP_VERIFY_PASS` e `DR13_REAL_RESTIC_VERIFIER_PASS`, `CP_DR13_ENGINE_CONTAINER_EXIT:0`.
- `tools/atlas-dr12-test-core.ps1`: **15 testes** de backup SQLite/contrato no contêiner Core descartável, baseline anterior.
- Todos os dados e senhas dos testes foram gerados/destruídos no contêiner isolado. Não representa restauração de dados reais.

## Orquestração e revisão independente
- Agente OpenCode DR13 (`20261013T120934Z-f8401a31`) analisou e tentou implementar tests/Restic. O primeiro patch verificava local incorreto `$RESTORE_DIR/sqlite/manifest.json`, não achava o manifesto em `/tmp/staging/.restic-backup.../sqlite`, e produzia falso PASS. O orquestrador **não aprovou o patch**: adicionou verificador seguro e executou teste Restic real independente. Os testes de manifesto inicialmente produzidos pelo agente eram inválidos e não foram aceitos como certificação.
- Agente de documentação (`20261013T121033Z-9c97f5cb`) entregou relatório; sua matriz foi revisada posteriormente para retirar contagens e estados imprecisos.
- Agente de auditoria (`20261013T121038Z-7faeb0fd`) executou em modo plan, sem autorização para gravar relatório fora de seu diretório; portanto não foi contabilizado como entrega em outbox.
- Nenhuma alteração de SSH keys, serviços live, backups reais, Git remoto, branch ou worktree.

## Pendências bloqueantes
1. Confirmar armazenamento durável criptografado, secrets provisionados com aprovação, rota offsite e permissões UID 65534.
2. Testar snapshot e restauração reais e verificáveis de **Pentium e Core**, com janela segura, integridade e rollback. Issue #11 segue P0 não certificada; status GitHub remoto não verificável (404).
3. Suíte e empacotamento locais agora verificados: `py -m pytest --import-mode=importlib infrastructure/pentium/atlas/tests infrastructure/pentium/agent/tests infrastructure/backup/tests -q` resultou em **1137 passed, 24 skipped, 53 subtests passed** (28.04s); `tools/atlas-dr11-build-core.ps1` retornou `RESTIC_BACKUP_PACKAGING_PASS` e `DISPOSABLE_PACKAGING_EXIT:0`; `git diff --check` exit 0. Esses testes não certificam o runtime físico. Para uma futura promoção, repetir tudo no SHA de integração aprovado.
4. Não ativar `homelab-backup.timer`, `self_healing_v1`, `agency_specialists.enabled` ou controles remotos por efeito colateral.
