# GDD Mestre — DevEx HomeLab

## 1. Visão do produto

O **DevEx HomeLab** é uma plataforma privada e versionada para operar o laboratório doméstico como uma extensão confiável do ambiente de desenvolvimento. O produto combina infraestrutura como código, control plane, compute containerizado, CI/CD, observabilidade, segurança, simulação local e documentação operacional.

## 2. Experiência desejada

O mantenedor deve conseguir desenvolver na x99, validar mudanças em um ambiente Docker que reproduz a topologia lógica do laboratório, enviar uma PR, receber evidência de CI no HEAD exato e, após aprovação, promover a versão para os nós corretos sem copiar arquivos manualmente.

A operação diária não pode depender da x99 estar ligada. Pentium e Core devem continuar operando de forma autônoma após uma versão aprovada ser implantada.

## 3. Pilares

### Developer Experience

- working copy canônica na x99;
- toolchains de projeto em containers sempre que tecnicamente possível;
- comandos e ambientes reproduzíveis;
- simulação de Core/Pentium/runners antes da certificação física.

### Control Plane

- Pentium observa estado e coordena ações allowlisted;
- nenhuma API de shell arbitrário;
- desired state vem do Git;
- observed state vem de GitHub API, Docker e health checks dos nós.

### Compute Platform

- Core hospeda workloads persistentes em Docker;
- um runner canônico por projeto: `core-<projectname>`;
- workspace, imagem e lifecycle isolados por projeto;
- toolchains de projeto não são instaladas como dependência do host.

### Governance

- documentação humana em pt-BR;
- arquitetura e PRD antecedem mudanças estruturais;
- todo estado permanente possui rastreabilidade;
- evidência de SHA anterior não promove HEAD atual;
- checkpoint registra implementação, CI, gates, blockers e próximo passo.

## 4. Topologia de produto

```text
x99 / DevEx workspace
        |
        v
GitHub private repository
        |
        +--> CI no core-devex-homelab
        |
        +--> artefatos/imagens versionados por SHA
        |
        v
Pentium control plane
        |
        v
Core compute / runners / serviços
```

## 5. Regras de ownership

O DevEx HomeLab é dono da infraestrutura, automações, imagens/stack de runners, observabilidade, segurança, inventário e processos de deploy do homelab.

Projetos hospedados continuam donos do próprio código, testes, workflows funcionais e regras de produto. Por exemplo, DevEx HomeLab é dono da stack `core-l2jtoren`, enquanto `deraldinho/L2jToren` é dono dos workflows e gates do L2jToren.

## 6. Modelo de entrega

Uma versão percorre:

```text
Issue → Design/PRD → branch → implementação → testes → PR
→ CI no HEAD exato → aprovação → deploy controlado
→ health/certificação → checkpoint → as-built
```

Tags de imagens implantáveis devem preferir SHA imutável. Rollback volta para uma versão previamente certificada.

## 7. Segurança

Secrets, chaves privadas, tokens de registro, credenciais de runner e autenticação Tailscale nunca são fonte de verdade no Git. O repositório registra contratos, nomes de secrets e políticas, não valores reais.

Docker socket é tratado como fronteira privilegiada. Workflows que o utilizarem precisam ser controlados e explicitamente autorizados.

## 8. Sucesso da foundation

A foundation é considerada pronta quando o repositório privado, documentação mestre, baseline as-built, simulação local, runner `core-devex-homelab`, CI no Core e observabilidade por projeto no Pentium estiverem certificados, mantendo x99 fora da dependência operacional e preservando o runner L2jToren durante sua migração separada.

## 9. Atlas — interação local do homelab

O `pentium` também hospeda o **Atlas**, camada local de percepção e interação do DevEx HomeLab. O Atlas consome observed state do control plane para representar a saúde do homelab inteiro, produzir uma linguagem sonora tecnológica variada e, por fases, oferecer voz local e interpretação por mini LLM.

A autoridade operacional continua determinística: LLM e memes são interfaces de interpretação/expressão, nunca substituem health gates, allowlists, confirmações ou políticas de segurança.
