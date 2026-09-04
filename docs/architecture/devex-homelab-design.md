# DevEx HomeLab — Design Arquitetural

## 1. Identidade do projeto

- Nome formal: **DevEx HomeLab**
- Repositório: `deraldinho/devex-homelab`
- Visibilidade: **private**
- Working copy canônica: `C:\Users\deral\DevEx-HomeLab`
- Fonte de verdade operacional: GitHub
- Política de execução: container-first
- Política de deploy: deploy controlado

## 2. Objetivo

O DevEx HomeLab é a plataforma versionada de infraestrutura e experiência de desenvolvimento do laboratório doméstico. Ele define, valida e documenta o estado desejado dos nós, runners, automações, redes de administração, observabilidade, segurança e fluxos de entrega.

O projeto não hospeda o código de produtos como L2jToren. Ele é proprietário da infraestrutura que executa esses produtos.

## 3. Nós e responsabilidades

### x99 — workstation

- Uso diário e desenvolvimento interativo.
- Working copy oficial do DevEx HomeLab em `C:\Users\deral\DevEx-HomeLab`.
- Docker/WSL2 usado para simular o ambiente lógico do laboratório.
- Não é dependência obrigatória da operação do homelab.

### core — homelab.compute

- Ubuntu 26.04.1 LTS.
- Docker/Compose como runtime principal.
- Hospeda um runner containerizado por projeto.
- Não recebe toolchains de projeto diretamente no host.
- Comunicação administrativa via Tailscale/SSH.

### pentium — homelab.control

- Ubuntu 26.04.1 LTS.
- Nó leve sempre ligado.
- Executa control plane, sentinel, jobs e observabilidade.
- Coordena health checks e deploys controlados.
- Não executa builds pesados.

## 4. Modelo de runners por projeto

Padrão obrigatório: `core-<projectname>`.

Estado inicial desejado:

- `core-devex-homelab` → CI do DevEx HomeLab.
- `core-l2jtoren` → CI do L2jToren.

Cada runner possui:

- container próprio;
- imagem CI própria;
- configuração GitHub Runner própria;
- volume `_work` próprio;
- logs e lifecycle próprios;
- labels específicas;
- política de restart própria.

Instâncias adicionais do mesmo projeto só recebem sufixo numérico quando necessário, por exemplo `core-l2jtoren-02`.

## 5. Container-first

O host Core permanece mínimo. JDK, Ant, Python de build, Node, Codex e demais toolchains de projetos ficam em imagens/containeres.

Checkouts persistentes de projetos não pertencem ao host Core. O workspace de CI vive em volumes Docker dedicados ao runner correspondente.

Na x99, o checkout físico permanece no Windows, mas validações e toolchains do DevEx HomeLab devem rodar em containers sempre que tecnicamente possível.

## 6. Ambiente de simulação na x99

O Docker da x99 representa o ambiente lógico do laboratório, não o hardware real.

Topologia simulada prevista:

```text
sim-core
sim-pentium
sim-core-devex-homelab
sim-core-l2jtoren
```

A simulação valida manifests, lifecycle, comunicação de serviços, health checks, scripts, Python, Compose e falhas controladas.

Não é considerada prova de comportamento do kernel, BIOS, Wi-Fi, NVMe, bateria, systemd real, Tailscale real, SSH daemon do host ou Wake-on-LAN.

## 7. Fonte de verdade e drift

GitHub descreve o **desired state**. Pentium e checks de host produzem o **observed state**.

Qualquer configuração permanente alterada manualmente e ausente do repositório é `drift`.

Tratamento:

1. se a alteração manual é válida, reconciliar o Git por Issue/PR;
2. se é inválida, restaurar o estado versionado.

A primeira fase não fará auto-remediação agressiva. Detectar, classificar, evidenciar e aprovar vem antes de corrigir automaticamente.

## 8. Deployment Architecture

### 8.1 Fluxo de promoção

```text
x99 -> GitHub -> PR -> CI -> GREEN no HEAD exato
                       -> artefato/imagem versionado por SHA
                       -> aprovação de deploy
                       -> Pentium coordena
                       -> Core/Pentium aplicam
                       -> health check
                       -> certificação
                       -> checkpoint
                       -> as-built
```

Mudanças sensíveis em SSH, rede, Tailscale, firewall, storage, Docker daemon e sistema operacional exigem aprovação explícita.

Mudanças de baixo risco em containers/manifests podem evoluir para deploy automatizado após gates específicos.

### 8.2 Distribuição por nó

**Core:** recebe imagens e manifests aprovados. Preferência por tags imutáveis baseadas no commit SHA. Rollback usa a tag SHA anterior certificada.

**Pentium:** recebe control plane, sentinel, health checks e manifests próprios. O Pentium coordena entregas via Tailscale/SSH com ações allowlisted.

**x99:** recebe o ambiente de desenvolvimento e simulação. Não participa da operação obrigatória após o merge/deploy.

### 8.3 Contrato de deployment

Cada componente implantável deve declarar:

- alvo (`core`, `pentium` ou `x99-dev`);
- versão/SHA;
- imagem ou artefato;
- configuração não secreta;
- referências para secrets externos;
- health check;
- política de rollback;
- evidência de certificação.

O inventário deve permitir responder sem ambiguidade qual componente pertence a qual nó.

### 8.4 Modos de entrega

1. **Normal:** CI GREEN → aprovação → Pentium coordena aplicação.
2. **Manual controlado:** mantenedor executa o mesmo manifest/versão aprovada por comando versionado.
3. **Emergência:** restauração direta para recuperar disponibilidade, seguida obrigatoriamente de Issue/PR de reconciliação.

Nenhum modo autoriza criar uma configuração paralela fora da fonte de verdade.

## 9. Segurança

Nunca versionar:

- SSH private keys;
- PATs/tokens GitHub;
- runner registration tokens;
- Tailscale auth keys;
- `.credentials`;
- `.runner`;
- passwords;
- secrets reais.

Tokens de registro são temporários. Docker socket não é exposto pela rede. Workflows não confiáveis não recebem Docker socket sem avaliação explícita.

## 10. CI do DevEx HomeLab

Runner canônico: `core-devex-homelab`.

Labels esperadas:

```text
self-hosted
Linux
X64
core
homelab
container
devex-homelab
```

Gates iniciais:

- validação YAML;
- `docker compose config`;
- build dos Dockerfiles;
- shellcheck;
- testes Python;
- secret scan;
- validação documental e links;
- validação Mermaid quando disponível;
- policy checks;
- smoke de containers;
- certificação do runner no HEAD exato.

## 11. Governança documental

Fluxo padrão:

```text
GDD
 -> Domain/Architecture Design
 -> PRD
 -> Implementation Design
 -> UML/contratos
 -> Issue
 -> branch
 -> implementação
 -> testes
 -> CI/evidências
 -> checkpoint da PR
 -> deploy controlado
 -> as-built
```

Mudanças pequenas podem usar documentação reduzida, mas nunca perdem Issue, PR, CI/evidência e checkpoint quando alteram estado permanente.

## 12. Fronteira com L2jToren

DevEx HomeLab é dono de:

- imagem/stack do runner `core-l2jtoren`;
- política de volumes/lifecycle;
- observabilidade e capacidade do runner;
- segurança e host integration.

L2jToren é dono de:

- código do produto;
- workflows do produto;
- testes do produto;
- labels usadas para selecionar o runner;
- gates funcionais e de arquitetura do produto.

## 13. Estado inicial a reconstruir

O primeiro ciclo deve registrar como as-built o que já existe:

- Core configurado com Docker e runner containerizado atual;
- runner atual do L2jToren ainda nomeado genericamente `core`;
- volume de workspace existente;
- Pentium agent e sentinel;
- comunicação Tailscale entre Pentium/Core/x99;
- x99 runner legado do L2jToren;
- política container-first já adotada;
- CI de certificação já criada na PR #757 do L2jToren.

A migração correta será reconciliar esse estado para `core-l2jtoren` e criar `core-devex-homelab`, sem remover x99 automaticamente.

## 14. Falhas e recuperação

### Core indisponível

Pentium deve distinguir host inacessível de Docker indisponível e runner offline. Nenhum deploy continua se o alvo não puder ser identificado com segurança.

### Runner indisponível

A presença do container não prova que o runner está utilizável. GitHub API é a fonte primária para `online` e `busy`; Docker é evidência complementar.

### Imagem incompatível

Uma nova imagem só promove após build/teste e certificação no HEAD exato. A versão anterior certificada permanece referência de rollback.

### Workspace corrompido

Limpeza é sempre escopada ao volume do projeto. Um runner nunca usa ou apaga `_work` de outro projeto.

### Control plane indisponível

O modo manual controlado pode aplicar a versão aprovada diretamente por Tailscale/SSH usando os mesmos manifests. Depois, o Pentium é reconciliado sem criar um segundo caminho permanente de configuração.

## 15. Observabilidade

Por runner/projeto, o sistema deve conseguir reportar:

- nome;
- projeto;
- GitHub runner ID;
- online/offline;
- busy;
- labels;
- container running/stopped;
- restart policy;
- imagem/tag atual;
- volume `_work`;
- última certificação conhecida quando disponível.

Por nó, registrar no mínimo reachability Tailscale, papel, serviços essenciais e estado de implantação conhecido.

## 16. Definition of Done da foundation

A foundation só estará concluída quando:

1. `deraldinho/devex-homelab` existir e for privado;
2. working copy canônica existir em `C:\Users\deral\DevEx-HomeLab`;
3. GDD, arquitetura, PRD, UML, implementation design e baseline as-built estiverem versionados;
4. Issues iniciais estiverem criadas;
5. PR de foundation existir e possuir checkpoint;
6. ambiente de simulação Docker da x99 estiver validado;
7. `core-devex-homelab` estiver registrado e containerizado;
8. CI do DevEx HomeLab estiver GREEN no HEAD exato;
9. Pentium conseguir reportar `core-devex-homelab` por nome/projeto;
10. `core-l2jtoren` estiver planejado como migração separada, sem quebra do runner atual;
11. nenhum secret estiver versionado;
12. documentação as-built refletir os três nós reais.
