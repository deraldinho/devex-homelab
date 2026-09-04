# Core — política container-first

- O host executa somente infraestrutura: Ubuntu, Tailscale, SSH, Docker/Compose e ferramentas administrativas mínimas.
- JDK, Ant, Node, Codex e demais toolchains pertencem às imagens dos projetos, nunca ao host.
- Código-fonte de projeto deve existir dentro de volumes Docker nomeados ou no filesystem do próprio container.
- Não usar bind mount de `~/projects`; esse diretório não existe por política.
- `~/homelab/stacks` contém somente manifests de infraestrutura/Compose.
- `~/homelab/backups` contém exportações e backups; não é workspace de desenvolvimento.
- Segredos não devem ser gravados em imagens nem versionados em manifests.
- Exposição de portas deve ser explícita; serviços internos devem preferir rede Docker e/ou Tailscale.
- Alterações permanentes no Core são reconciliadas a partir deste repositório, nunca tratadas como configuração manual canônica.
