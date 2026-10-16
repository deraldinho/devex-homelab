---
name: atlas-opencode-orchestration
description: Orquestrar agentes OpenCode no repositório canônico DevEx-HomeLab do Atlas, com TDD, validação de sessões, prevenção de loops e preservação do contexto.
compatibility: opencode
metadata:
  project: DevEx-HomeLab
  host: x99
---
# Atlas: execução OpenCode governada

## Local fixo
- Raiz oficial do projeto Atlas: `C:\Users\deral\DevEx-HomeLab` no Windows x99.
- Código principal já existente: `infrastructure\pentium\atlas`.
- `C:\Users\deral\Documents\Atlas-DevOps` é um staging histórico e NÃO é o projeto oficial.
- Candidatos migrados residem em `tools\atlas-devops-recon` dentro do repositório correto; NÃO são runtime pronto.
- Nunca criar outro projeto, clone, worktree, branch paralela nem mover código para fora da raiz. Criar apenas arquivos necessários dentro da estrutura existente. Não sobrescrever o trabalho do usuário.

## Preflight obrigatório
1. Com Remote Desktop Commander confirmar x99 online. Executar `git rev-parse --show-toplevel` e verificar raiz exata; abortar se divergir.
2. Conferir `git status --short`, README, documentação, código e testes pertinentes. Não usar reset/clean.
3. Consultar `opencode service status`, `opencode api GET /api/info`, sessões e processos antigos.
4. Preferir CLI/API local autenticada. Não divulgar ou extrair senha, token ou link de pareamento.

## Sessões e contexto
- Criar sessões via `opencode api POST /api/session --data ...` com `location.directory` no JSON igual a `C:/Users/deral/DevEx-HomeLab`. No PowerShell, validar escape JSON. Nunca omitir location nem usar barras invertidas duplicadas.
- Para implementar, iniciar sessão NOVA com `agent=build`; para auditoria somente leitura, `agent=plan`. Não herdar uma sessão plan via fork para pedir código.
- Confirmar por `opencode api GET /api/session/<id>` que o caminho retornado normaliza para a raiz real e o projectID pertence ao repositório correto.
- Despachar por `POST /api/session/<id>/prompt` usando `text`, `agent` e `model`. `delivery=steer` não demonstra execução.
- Verificar `GET /api/session/<id>/message`, ferramentas executadas, resposta terminal, diffs e testes. Uma sessão succeeded isolada também NÃO certifica alterações funcionais.
- Conferir modelo realmente executado; preferir gratuitos, fallback somente com diagnóstico e controle de custo.

## Proteção contra loops
- Estabelecer timeouts de execução e inatividade, heartbeat, número máximo de tentativas e deduplicação por missão. Não disparar várias instâncias `--standalone`.
- Quando ficar travado, não criar agentes adicionais: inspecionar sessões/processos, logs sanitizados e reconciliar resultado ambíguo antes de retry.
- Encerrar somente PID comprovadamente associado à missão do Atlas. Não matar OpenCode desktop, servidor principal (observado PID 5168, mas deve ser redescoberto) nem processos de outros projetos.

## Engenharia e aceite
- Planejar a mudança no runtime EXISTENTE, mapear duplicatas e riscos, delegar trabalhos independentes e supervisionar.
- Usar TDD, segurança por padrão, aprovação de ações sensíveis e revisão independente. Preservar tudo que estiver modificado/não rastreado.
- Validar resultados com testes, git diff --check, evidência de artefatos, documentação e relatório. Não promover a produção nem declarar tudo pronto apenas porque testes locais passaram.
- Não realizar commit, push, deploy, restart ou mudanças destrutivas sem autorização correspondente.
- Se contexto entre conversas estiver ausente, reler este SKILL.md como fonte persistente.

## Integração preferencial no projeto existente (validada em 2026-10-15)
- Antes de implementar um novo orquestrador, inspecionar `tools/atlas_opencode_api.py`, `tools/atlas-opencode-bridge.ps1`, `.atlas/opencode` e `tools/test_atlas_opencode_api.py`. O bridge já dispõe de inbox/outbox, trava única, reconciliação, validação de tarefa e resultado terminal.
- Preferir esse mecanismo já testado em vez de criar sessão ad hoc sem consumidor, fila própria concorrente ou servidor `--standalone`.
- Nunca reutilizar relatórios de outra tarefa: vincular Task-Id, escopo, sessão, arquivo de status e evidência real.
- Teste inicial obrigatório: `python -m unittest discover -s tools -p test_atlas_opencode_api.py -v`; baseline observado: 20 testes OK em 2026-10-15.
- Registrar resultado e alterações diretamente nos diretórios existentes do DevEx-HomeLab; não duplicar módulos do staging em runtime sem auditoria de sobreposição.
