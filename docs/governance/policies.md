# Políticas de Governança

## Branch e PR

- `main` é a linha integrada.
- Mudanças de estado permanente entram por branch e PR.
- Não promover HEAD com check obrigatório pending, queued, in_progress ou RED.
- Não reutilizar evidência de SHA anterior como gate do HEAD atual.
- PRs de infraestrutura começam como Draft enquanto houver gates pendentes.

## Fluxo documental

```text
GDD → Domain/Architecture Design → PRD → Implementation Design
→ UML/contratos → código/IaC → testes → CI/evidências
→ checkpoint → deploy controlado → as-built
```

O nível de documentação acompanha o risco; mudanças pequenas não precisam duplicar documentos, mas não podem perder rastreabilidade.

## Checkpoint

Após cada slice, registrar comentário `/checkpoint` contendo:

- HEAD exato;
- implementação concluída;
- validações e CI;
- gates/blockers;
- riscos conhecidos;
- próximo passo único.

## Fonte de verdade e drift

Git descreve desired state. Estado permanente divergente no host é drift até ser reconciliado por PR ou revertido ao estado versionado.

## Segurança

Secrets reais nunca entram em Git, Issues, PRs ou logs deliberados. Arquivos locais de credenciais devem permanecer ignorados e fora dos manifests.

## Deploy

Deploy é controlado. Alterações sensíveis em rede, SSH, Tailscale, storage, firewall, Docker daemon ou sistema operacional exigem aprovação explícita antes de tocar o host.

## Emergência

Correção manual é permitida para recuperar disponibilidade. Depois, abrir reconciliação para registrar o estado final no Git e eliminar drift.
