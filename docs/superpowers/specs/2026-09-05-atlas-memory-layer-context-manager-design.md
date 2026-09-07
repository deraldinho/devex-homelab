# Atlas Memory Layer v1 + Automatic Context Manager — Design

## Objetivo

Adicionar memória local persistente e bounded ao Atlas sem transformar a LLM em dona da memória.
A memória deve sobreviver a restart, permitir recuperação relevante e degradar com segurança sob pressão.

## Princípios

- A LLM nunca grava, altera ou apaga memória diretamente.
- Escrita, promoção, compactação e remoção são decisões determinísticas do MemoryManager.
- Persistência local em SQLite; sem vector database no v1.
- O ContextoCognitivo continua bounded e é a única visão da memória entregue à LLM.
- Memórias protegidas/pinned nunca sofrem eviction automática.
- Corrupção ou indisponibilidade da memória não impede o Atlas de operar sem memória.

## Camadas

- L0 WORKING: contexto imediato de interação, curto prazo e expiração rápida.
- L1 EPISODIC: acontecimentos, conversas relevantes, incidentes e experiências.
- L2 SEMANTIC: fatos estáveis consolidados e aprendidos.
- L3 RELATIONAL: informações de vínculo, familiaridade, confiança e expectativas.

Cada registro possui id, camada, timestamp, entidade, conteúdo reduzido, importância, confiança,
frequência, origem, pinned/protegida, expires_at e chave de deduplicação.
## Automatic Context Manager

O gerenciador mede ocupação lógica da memória e age antes de saturação:

- abaixo de 70%: operação normal;
- 70–85%: remover expiradas e deduplicar;
- 85–95%: consolidar episódios repetidos e promover fatos estáveis;
- acima de 95%: eviction controlada por score, somente de itens não protegidos;
- em 100%: rejeitar novas memórias descartáveis e preservar protegidas.

O score de retenção é determinístico e considera importância, confiança, frequência, criticidade,
vínculo e recência. O v1 não usa a LLM para calcular esse score.

## Persistência

SQLite em modo WAL quando suportado. Todas as operações de consolidação são transacionais.
A memória consolidada é persistida antes da remoção dos episódios de origem.
O schema é versionado e migração incompatível falha fechado sem destruir o banco existente.

## Recuperação

MemoryRetriever consulta por camada, entidade e termos normalizados, ordena por relevância e limita
quantidade e bytes. FTS5 pode ser usado quando disponível; o fallback é consulta estruturada.
Nenhuma busca retorna histórico ilimitado.
## Integração cognitiva

MemoryRetriever roda antes do ContextoCognitivoBuilder.
O builder recebe somente memórias já reduzidas e acrescenta `memorias_relevantes` ao contexto.
Esse campo possui quantidade e bytes próprios e participa do limite global do ContextoCognitivo.
Se o payload exceder o orçamento, memórias de menor score são removidas antes de campos obrigatórios.

## Escrita de memória

Entradas podem vir de eventos determinísticos, interação humana ou resultados validados de capability.
A LLM pode sugerir uma `MemoryCandidate`, mas a sugestão não é persistida automaticamente.
O MemoryManager valida origem, schema, limites, duplicidade e política antes de salvar.

## Segurança e privacidade

- sem shell, SSH, rede ou leitura arbitrária de arquivos;
- conteúdo por registro é limitado;
- nenhuma credencial, segredo ou payload bruto deve ser memorizado;
- memórias de identidade/configuração crítica podem ser `protegida=true`;
- exclusão automática nunca remove item protegido.

## DoD M1

- SQLite schema/versionamento e recuperação após restart;
- L0–L3 representadas explicitamente;
- deduplicação, expiração, compactação e eviction testadas;
- comportamento 70/85/95/100% testado;
- MemoryRetriever bounded integrado ao ContextoCognitivo;
- corrupção/falha do store não derruba Reaction Loop;
- installer/CI empacotam M1 e emitem marker próprio;
- nenhuma certificação física é declarada por esta slice.