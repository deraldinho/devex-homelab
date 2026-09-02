## Objetivo

Descreva a mudança e a Issue vinculada.

## Estado desejado

Explique qual desired state será alterado e quais nós/componentes são afetados.

## Evidências

- HEAD exato:
- testes locais/containerizados:
- CI/checks:
- certificação física, quando aplicável:

## Segurança e deploy

- [ ] nenhum secret foi versionado
- [ ] rollback foi definido quando a mudança é implantável
- [ ] mudança sensível exige aprovação explícita
- [ ] x99 não foi introduzida como dependência operacional

## Gate

Não promover enquanto check obrigatório estiver pending/queued/in_progress/RED ou enquanto a evidência não pertencer ao HEAD atual.

## Checkpoint

Adicionar `/checkpoint` após cada slice concluída.
