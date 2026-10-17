# Atlas CP-DEPLOY01 - Plano de Rollback

## Serviços a serem reiniciados em caso de falha
- atlas-cognitive.service
- atlas-observation.service
- atlas-discord.service
- atlas-dashboard.service

## Procedimento de Rollback
1. Parar serviços afetados:
   systemctl --user stop atlas-cognitive atlas-observation atlas-discord

2. Restaurar módulos do backup:
   cp /home/deraldinho/atlas-backup-pre-deploy/*.py /home/deraldinho/pentium-agent/atlas/

3. Reiniciar serviços:
   systemctl --user restart atlas-cognitive atlas-observation atlas-discord

4. Verificar serviços:
   systemctl --user is-active atlas-cognitive atlas-observation atlas-discord

## Backup localizado em
/home/deraldinho/atlas-backup-pre-deploy/

## Backup remoto (Restic)
/home/deraldinho/atlas-backup/restic-repo
Snapshot: 31312528 (21:38:54, 24.252 MiB)
