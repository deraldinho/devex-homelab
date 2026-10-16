# Atlas / OpenCode — canal HTTPS privado e relatorios por projeto

Data local: 2026-10-12 (America/Sao_Paulo)
Estado: canal validado; somente para tarefas explicitamente iniciadas.

## Arquitetura

- Entrypoint: `tools/atlas-opencode-bridge.ps1`.
- Transporte padrao: `tools/atlas_opencode_api.py` (Python 3, biblioteca padrao).
- Endpoint permitido: `https://x99.tail2ffe44.ts.net`, acessivel apenas via Tailscale Serve.
- Senha: obtida da configuracao local OpenCode; nao transmitida por parametro de processo ou gravada na outbox.
- Cada projeto mantem `.atlas/opencode/inbox`, `outbox`, `tmp`, `archive` e README.
- Uma tarefa usa ID imutavel; a API cria sessao com `location.directory` explicito, envia o pedido e consulta `GET /api/session/{id}`.
- `-Mode reconcile` consulta uma sessao anterior apos timeout e verifica o relatorio sem reenviar o pedido. Somente status `reported` representa entrega validada.

## Evidencia do teste local real

- Task-Id: `20261013T020603Z-b6184f61`.
- Session-Id: `ses_eccfd5f7dffekz1aQUyJnuDorT`.
- O invocador criou uma sessao real pela VPN e o OpenCode gravou o arquivo `.atlas/opencode/outbox/20261013T020603Z-b6184f61.md`.
- Houve timeout antes da conclusao; o OpenCode entregou o arquivo apos o limite.
- Uma reconciliacao da sessao (sem reenvio) retornou `reported` e `report_exists=true`.
- `py -m unittest tools.test_atlas_opencode_api -q`: 11 testes aprovados.
- Parser do `atlas-opencode-bridge.ps1`: 0 erros.
- `git diff --check`: sem erros no momento da verificacao.

## Limites e observacoes

- O modelo pode produzir afirmacoes incorretas no proprio relatorio. O smoke test apresentou alegacoes de que o agente nao dispunha de acesso VPN, embora a sessao tivesse sido criada pela API HTTPS privada. O relatorio e evidencia de execucao; suas conclusoes precisam ser auditadas.
- O projeto deve manter os gates Backup/DR P0 e CP-H12 para mudancas de producao e automacao viva.
- Nao houve autorizacao para alterar perfis Hermes, reiniciar servicos, publicar endpoints na internet, fazer push ou criar worktrees.
- O endpoint HTTPS e autorizado na tailnet; fora dela a conectividade e a autenticacao devem falhar.
