# Core Runner Pool v2 — Design

Data: 2026-09-06
Status: aprovado em conversa, aguardando revisão do documento
Repositório autoritativo: `deraldinho/devex-homelab`

## 1. Objetivo

Transformar o Core no host oficial dos runners GitHub Actions do homelab, retirando o x99 da função obrigatória de CI após certificação da nova topologia.

A topologia alvo possui três runners containerizados independentes:

- `core-l2jtoren-01` para `deraldinho/L2jToren`;
- `core-l2jtoren-02` para `deraldinho/L2jToren`;
- `core-homelab-01` para `deraldinho/devex-homelab`.

Os dois runners L2jToren formam um pool homogêneo de capacidade 2. O runner do homelab permanece isolado por projeto.

## 2. Princípios arquiteturais

1. Isolamento por projeto: L2jToren e DevEx HomeLab não compartilham runner, workspace nem credencial de registro.
2. Isolamento por instância: cada runner possui container, workspace, estado e identidade GitHub próprios.
3. Roteamento por capacidade: workflows deixam de depender apenas de `self-hosted`.
4. Nenhum token de registro permanente é versionado no Git.
5. O Core é compute plane de CI; Pentium mantém seus papéis de control plane/Atlas; x99 torna-se workstation/fallback administrativo.
6. Nenhuma migração desativa o runner antigo antes de a nova topologia estar certificada.
## 3. Topologia

```text
GitHub Actions
      |
      v
CORE — Docker host
      |
      +-- core-l2jtoren-01  -> L2jToren
      +-- core-l2jtoren-02  -> L2jToren
      +-- core-homelab-01   -> devex-homelab
```

Cada container executa exatamente um GitHub Actions Runner Listener. Não haverá multiplexação de duas identidades de runner no mesmo container.

## 4. Imagens

### 4.1 L2jToren

Os runners `core-l2jtoren-01` e `core-l2jtoren-02` usam a mesma imagem versionada. A imagem deve conter no mínimo JDK 26, Ant, Git, Python, Docker CLI, Docker Compose e ferramentas exigidas pelos workflows vigentes do L2jToren.

A imagem não contém credenciais do GitHub. O registration token é obtido no provisionamento e usado apenas para registrar a instância.

### 4.2 DevEx HomeLab

`core-homelab-01` usa imagem própria, contendo apenas as dependências necessárias ao projeto: Python, Git, shell tooling e Docker CLI/Compose quando exigido pelos workflows. Dependências específicas do L2jToren não pertencem a esta imagem.

## 5. Workspaces e persistência

Cada instância terá volume de workspace exclusivo:

- `core-l2jtoren-01-work`;
- `core-l2jtoren-02-work`;
- `core-homelab-01-work`.

Nenhum `_work` é compartilhado entre runners. Isso evita contaminação de checkout, artefatos, locks, caches transitórios e limpeza concorrente.
## 6. Labels e roteamento

### 6.1 L2jToren

Labels mínimas planejadas:

- `self-hosted`
- `Linux`
- `X64`
- `core`
- `container`
- `l2jtoren`
- `docker`

Os workflows gerais que dependem de Docker devem selecionar capacidade, não identidade física específica:

```yaml
runs-on: [self-hosted, core, l2jtoren, docker]
```

Os dois runners podem satisfazer o mesmo selector e o GitHub distribui jobs entre eles.

### 6.2 Workloads pesados

Benchmarks de capacidade, soak e gates sensíveis a contenção receberão uma label adicional, por exemplo `l2jtoren-heavy`. Inicialmente apenas um runner terá essa label, impedindo dois benchmarks pesados concorrentes de contaminarem a evidência de capacidade.

### 6.3 DevEx HomeLab

Labels mínimas planejadas:

- `self-hosted`
- `Linux`
- `X64`
- `core`
- `container`
- `devex-homelab`

Selector recomendado:

```yaml
runs-on: [self-hosted, core, devex-homelab]
```
## 7. Docker dentro dos runners

Os containers de runner terão acesso ao Docker host do Core por interface explicitamente definida no provisionamento. O design não autoriza DinD privilegiado por padrão.

O acesso ao daemon será tratado como capability de infraestrutura e só será concedido às imagens que realmente executam workflows com Docker. A certificação deve provar `docker version`, `docker compose version` e execução de container descartável antes de aplicar a label `docker`.

Nomes de redes, projetos Compose e containers criados por CI devem incorporar identidade única de run/job para impedir colisão entre `core-l2jtoren-01` e `core-l2jtoren-02`.

## 8. Registro e segredos

Cada runner é registrado individualmente no repositório correspondente. Registration tokens são efêmeros e não podem aparecer em imagem, Compose versionado, arquivo `.env` commitado, log persistente ou documentação.

Estado operacional e segredos permanecem fora do Git. O repositório versiona somente Dockerfiles, manifests, scripts de provisionamento sem segredo, políticas e testes de certificação.

## 9. Health e lifecycle

Cada container deve usar política de restart apropriada e possuir healthcheck que não confunda processo de bootstrap com runner registrado e saudável.

O lifecycle esperado é:

1. container inicia;
2. valida dependências locais;
3. registra ou recupera identidade autorizada conforme estratégia de provisionamento;
4. inicia um único Runner Listener;
5. publica health somente quando apto a receber jobs;
6. em shutdown, encerra listener de forma ordenada.

Recriação de container não pode criar runners órfãos indefinidamente no GitHub.
## 10. Certificação

Nenhum runner recebe status autoritativo apenas por aparecer `online` no GitHub. A certificação mínima por instância deve validar:

- identidade e labels esperadas;
- arquitetura Linux/X64;
- Git;
- toolchain específica do projeto;
- Docker/Compose quando aplicável;
- container smoke quando aplicável;
- checkout e execução de workflow real no repositório-alvo;
- workspace exclusivo;
- ausência de colisão entre os dois runners L2jToren.

Para o L2jToren, a migração somente é considerada fechada quando um mesmo conjunto de workflows consegue distribuir jobs entre `core-l2jtoren-01` e `core-l2jtoren-02` e o `CI Runtime` anteriormente RED executa além da etapa de validação de capacidades.

## 11. Migração

Ordem obrigatória:

1. versionar imagem/manifests do L2jToren;
2. subir e certificar `core-l2jtoren-01`;
3. subir e certificar `core-l2jtoren-02`;
4. executar teste de concorrência e isolamento;
5. versionar/subir/certificar `core-homelab-01`;
6. migrar selectors dos workflows L2jToren;
7. migrar selectors dos workflows DevEx HomeLab;
8. rerodar gates reais, incluindo o CI Runtime da PR autoritativa vigente do L2jToren;
9. somente após evidência GREEN, retirar o runner da x99 da função de CI obrigatória;
10. remover registro legado quando não houver job ativo nem dependência residual.

## 12. Papel dos nós após a migração

- Core: compute plane oficial de GitHub Actions containerizado.
- x99: workstation, desenvolvimento, diagnóstico, testes manuais e fallback administrativo; não é gate obrigatório de CI.
- Pentium: control plane/Atlas/observabilidade conforme arquitetura do homelab; não recebe workloads pesados de build por esta mudança.
## 13. Fora de escopo

Esta mudança não altera a Architecture vNext do servidor L2jToren, não mistura código entre os dois repositórios e não cria dependência de Atlas dentro do CI do L2jToren.

Também não redefine os gates funcionais dos projetos. Ela altera somente onde e como os jobs self-hosted são executados e certificados.

## 14. Critérios de conclusão

A implementação estará concluída quando:

- os três runners estiverem registrados e GREEN;
- os dois L2jToren suportarem jobs concorrentes sem compartilhar workspace;
- workflows selecionarem runners por labels de projeto/capacidade;
- workload Docker executar em ambos os runners L2jToren certificados;
- workload pesado possuir isolamento explícito de capacidade;
- `core-homelab-01` executar o Foundation CI do homelab;
- a PR autoritativa vigente do L2jToren conseguir executar o CI Runtime além do antigo blocker `docker: command not found`;
- nenhum gate dependa obrigatoriamente do x99;
- a remoção do runner legado da x99 ocorra somente após essas evidências.

## 15. Decisão

Adotada a estratégia de três containers de runner independentes no Core: dois dedicados ao L2jToren e um dedicado ao DevEx HomeLab, com imagens, workspaces, identities, labels e lifecycle isolados por projeto/instância.
