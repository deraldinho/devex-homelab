# Atlas — backup real no Pentium (2026-10-13)

**Estado:** backup local criptografado funcionando, restauração isolada validada, timer de usuário habilitado e ativo. **Offsite e proteção contra falha física do disco não certificados.**

## Proteção
- Fontes reais: `/home/deraldinho/atlas` e `/home/deraldinho/.hermes`.
- Restic 0.18.1 em `/home/deraldinho/.local/bin/restic`; SQLite da distribuição em `/usr/bin/sqlite3`.
- Repositório local criptografado em `~/.local/share/atlas-restic/repository`.
- Chave gerada pelo próprio Pentium em `~/.config/atlas-backup/restic.password` (permissões restritas). **Não copiar a senha para o GitHub, relatórios ou chat.**
- Script do backup em `~/.local/share/atlas-backup/backup.sh`, espelhado em `tools/atlas-pentium-backup.sh` no x99.
- O script usa `sqlite_snapshot.py` para copiar os bancos transacionalmente para um estágio privado; arquivos DB originais e WAL/SHM são excluídos do Restic. Backup protegido por flock; sem `restic unlock`, `forget`, `prune` automáticos.
- Observação: `~/.hermes` contém dados privados e possíveis credenciais do agente. Eles ficam cifrados no repositório local; tratar todo restore e o arquivo de senha como secretos.

## Certificação observada
1. `restic init` seguro concluído uma única vez: `ATLAS_PENTIUM_REPOSITORY_INIT_OK`.
2. Primeiro backup real: **25.691 arquivos**, 930,121 MiB lidos, 360,524 MiB persistidos; snapshot `549a7735`. `restic check --read-data-subset=2%`: **no errors found**, `ATLAS_PENTIUM_BACKUP_OK`.
3. Restic `restore` em pasta privada isolada: 29.434 objetos restaurados de 930,121 MiB. Verificação transacional independente por `sqlite_snapshot.restore` restaurou **2 bancos SQLite**, ambos aprovados no `PRAGMA integrity_check`. Confirmações: `ATLAS_PENTIUM_SQLITE_TRANSACTIONAL_RESTORE_PASS 2` e `ATLAS_PENTIUM_FILES_AND_DB_RESTORE_PASS`.
4. O verificador DR-13 genérico recusou a árvore completa (que contém symlinks/estrutura real). **Não foi desabilitada sua restrição**: usou-se validação específica do manifesto transacional em uma cópia isolada. A robustez do verificador genérico para restore real é um follow-up.
5. Serviço `systemctl --user start atlas-pentium-backup.service`: `Result=success`, `ExecMainStatus=0`, segundo snapshot `787d89e8`.
6. Timer `atlas-pentium-backup.timer` **enabled + active**; próxima execução exibida: **2026-10-14 03:02:24 -03** (03h diário com jitter de até 15 min; persistent).
7. Nenhum serviço Atlas/Hermes foi reiniciado, nenhuma porta foi alterada. Instalação sem sudo em unidade `systemd --user`.

## Auditoria e riscos restantes
- **P0:** backup/repositório/senha estão no mesmo disco do Pentium. Uma falha, perda ou comprometimento da máquina pode eliminar cópia e chave. Implantar um segundo repositório *externo*, com chave e permissões adequadas, e certificar restore usando essa cópia.
- O backup exclui bancos originais para evitar capturar páginas inconsistentes; ao restaurar, executar restauração transacional dos bancos para o diretório certo, em isolamento antes do cutover. Não sobrepor arquivos vivos.
- O repositório local não tem pruning automático (intencional por segurança). Monitorar espaço e elaborar retenção conservadora **depois** de obter cópia externa testada.
- O timer pertence ao gerenciador systemd do usuário; `loginctl show-user deraldinho -p Linger` retornou **Linger=yes**, sem mudanças. Persistência após reboot ainda não foi submetida a ensaio físico.
- Serviços Atlas existentes não foram modificados e o checkpoint CP-H12 de recuperação operacional completa continua pendente.
