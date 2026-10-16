# Atlas 5.0 — CP-DR16 e CP-DEPLOY01: reparos independentes
Data de execução: 2026-10-13 (America/Sao_Paulo). Root x99: `C:\Users\deral\DevEx-HomeLab`.
Nenhuma nova branch, worktree, commit, push ou deploy do código cognitivo.

## CP-DR16 — verificação de restauração Restic com dois estágios ACID
**Falha reproduzida:** o backup real Pentium passou a capturar dois conjuntos transacionais, `sqlite-hermes` e `sqlite-live`, mas o verificador genérico `infrastructure/backup/verify_sqlite_restore.py` só aceitava um manifesto com basename `sqlite`. O teste novo falhou em RED (`orphaned_transactional_images`).

**Correção no repositório:**
- Aceita formato histórico com **um** estágio `sqlite` ou novo formato com **ambos** `sqlite-hermes` + `sqlite-live`.
- Exige que os dois manifestos provenham do **mesmo** diretório privado `.restic-backup.XXXXXXXX`.
- Nega estágio novo parcial, misturas entre formato antigo/novo, múltiplos roots, DB cru junto de stage, symlinks e imagens órfãs.
- Reconstrói bancos em destinos privados **separados por stage**, evitando colisão de nomes. Formato antigo mantém layout anterior.
- Sem acesso a bancos vivos, sem restore sobre produção e sem relaxar o orçamento de arquivos.

**Provas:** `infrastructure/backup/tests/test_verify_sqlite_restore.py`: **14 passed, 1 skipped**; novos testes para ambos os estágios, estágio incompleto, misto e raízes distintas. `tools/atlas-dr13-real-restic-core.ps1`: Restic **real com dados sintéticos**, executado em contêiner descartável isolado no Core, **exit 0/validated**, sem mounts ou credenciais reais; evidência `.atlas/opencode/tmp/cp-dr16-core-real-restic.log`. A prova de restauração do Pentium com dados reais e três bancos SQLite já foi registrada no CP-DR15 e não foi sobrescrita.

## CP-DEPLOY01 — gate read-only de divergência antes do deploy
Criados `tools/atlas_deploy_gate.py` e `tools/test_atlas_deploy_gate.py`.
O script compara SHA256 de módulos Python de topo do repositório com manifesto somente de hashes previamente colhido do runtime **real**, preserva explicitamente módulos exclusivos do host e **nunca** autoriza execução de deploy (mesmo quando hashes coincidem). Rejeita entradas malformadas, path traversal, symlink, digests inválidos e falta dos três entrypoints críticos. Não tem código de SSH/escrita no host.

**Provas:** 6 passed, 1 skipped, 2 subtests passed. No manifesto registrado em `.atlas/opencode/tmp/atlas-pentium-source-hashes.json`, a classificação real foi **HOLD_DRIFT_REQUIRES_PLAN**: 177 módulos repo, 168 módulos live, **7 diferentes**, **13 ainda não instalados**, **4 host-only preservar**. Relatório em `.atlas/opencode/tmp/cp-deploy-gate-actual.json`. Atenção: este manifesto foi colhido antes desta execução; atualizar hashes no Pentium no momento do plano de rollout. Gate não cobre recursos/subpacotes/configs/unidades systemd e não substitui teste de rollback.

## Hermes físico: fatos observados nesta execução
Com SSH autenticado, `python3 -m atlas.hermes_preflight` no `~/pentium-agent` retornou **ATLAS_HERMES_PREFLIGHT_PASS**; Hermes encontrado em `~/.local/bin/hermes`; config instalada apresenta `provider=None` (delegação de modelo ao Hermes), `profile=atlas` e `timeout_s=45.0`. Esses fatos **não** provam resposta LLM efetiva.

**Bloqueio para pesquisa web:** `prepare-hermes-atlas.sh` desativa explicitamente `web`, `search`, `browser`, `memory` e demais ferramentas do perfil atlas, como barreira de segurança. O módulo `web_research_policy.py` valida referências de forma estática e **não** implementa busca. Pesquisa web real continua pendente, sem autorizar ferramentas arbitrárias do Hermes.

## CP-CONV01 e QA
OpenCode acionado com `opencode/mimo-v2.6-flash-free`, `-TimeoutSeconds 900` para integração conversacional offline; Task-Id `20261014T010448Z-f8907c00`. Agente final QA read-only enfileirado (Task-Id `20261014T010916Z-f799c9f4`) para execução **após conclusão da implementação**, sem sobrepor as sessões no mesmo projeto. Os estados finais devem ser reconciliados e verificados; não marcar como entregue somente por estar em `session_created`.

## Gates de rollout
1. Só promover código cognitivo após CP-CONV01 PASS e QA independente.
2. Analisar migração dos 7 arquivos divergentes e preservar 4 host-only.
3. Verificar assinatura/hash de artefato, memória, conversa e policy de capabilities em staging; confirmar backup DR15, restore isolado, rollback.
4. Pesquisa web segue desabilitada até implementação de ferramenta read-only com DNS/TLS, fontes e proteção SSRF.
5. Agência AA7/controle/self-healing seguem em default-deny. Backup local em uso, offsite P0.


## Adendo: motor Restic verdadeiro com DOIS estágios (Core descartável)
Para complementar o teste unitário dual e a regressão Restic antiga de estágio único, foi criada e executada `tools/atlas-dr16-dual-real-restic-core.ps1` no Core, usando contêiner Docker temporário com `--network none`, `--read-only`, usuário 65534, `--cap-drop ALL`, sem binds de volumes produtivos nem chaves reais. O teste gera dois bancos SQLite sintéticos em origens independentes, cria as imagens transacionais, faz **Restic real init+backup+restore**, recusa cópia de SQLite bruto e exige que o novo verificador reconstrua os dois bancos em diretórios separados, confirme seu conteúdo e passe `PRAGMA integrity_check`.

**Resultado:** `DR16_DUAL_SQLITE_REAL_RESTIC_PASS`, `DR16_DISPOSABLE_CORE_EXIT:0`; o wrapper retornou `{"status":"synthetic_engine_pass","core_docker_exit":0,"production_restore":false}`. Evidência: `.atlas/opencode/tmp/cp-dr16-dual-real-restic.log`. Isto **não** substitui a restauração real em Pentium nem certifica destino offsite.
