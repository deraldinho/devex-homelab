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

## Gate de coerencia arquitetural e regras de negocio

- Antes de iniciar cada slice, confirmar que o desenho proposto preserva ownership, limites bounded, fail-safe, seguranca e responsabilidades das camadas vigentes.
- Cada regra de negocio nova ou alterada deve ser rastreada para o componente arquitetural que a implementa e para testes que comprovem o comportamento.
- Divergencia entre codigo, arquitetura, PRD/regra de negocio ou governanca e blocker: parar a implementacao ou promocao e reconciliar a fonte de verdade antes de prosseguir.
- Antes de marcar PR Ready ou promover um HEAD, repetir a verificacao arquitetura <-> regras de negocio sobre o diff final.

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

## Proteção de Hardware e Controle de Escopo

1. O nó `pentium` (`homelab.control`) é estritamente reservado para observabilidade leve, heartbeat e sentinel determinístico.
2. Cargas pesadas de processamento (LLM, Whisper STT, TTS, compilações pesadas, renderização contínua) são terminantemente proibidas de executar diretamente no host do Pentium e devem ser alocadas em containers dedicados no `core` (`homelab.compute`).
3. Nenhuma feature adicional de automação ou subsistema experimental poderá ser promovida enquanto as issues fundacionais P0 (notadamente Issue #11 Backup/DR) permanecerem pendentes.
4. O empacotamento de artefatos de software deve ser 100% declarativo e atômico (container-first ou pyproject/pip). É proibido o uso de laços manuais de arquivos hardcoded em scripts bash para instalação em nós físicos.

