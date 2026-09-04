# DevEx HomeLab

Fonte de verdade operacional do laboratório doméstico de desenvolvimento.

## Identidade

- Projeto: **DevEx HomeLab**
- Repositório: `deraldinho/devex-homelab` (privado)
- Working copy canônica: `C:\Users\deral\DevEx-HomeLab`
- `pentium`: `homelab.control`
- `core`: `homelab.compute`
- `x99`: workstation de desenvolvimento, fora da dependência operacional obrigatória

## Princípios

- container-first;
- Git como desired state;
- mudanças permanentes por Issue → PR → CI/evidência → checkpoint → as-built;
- deploy controlado;
- administração entre nós via Tailscale/SSH;
- nenhum secret real versionado;
- runners no Core seguem `core-<projectname>`.

## Documentação

Comece por [`docs/README.md`](docs/README.md). A foundation está rastreada pela Issue #1.
