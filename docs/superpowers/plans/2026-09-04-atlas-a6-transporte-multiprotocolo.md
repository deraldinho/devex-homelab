# Atlas A6 Transporte Multiprotocolo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar A6 com envelope remoto, sessão/replay/idempotência e três transportes reais seguros: TCP/mTLS, gRPC streaming/mTLS e HTTPS/mTLS.

**Architecture:** O A5 permanece responsável por IPC local, validação inicial e fila bounded. A6 adiciona um envelope remoto comum, política criptográfica de identidade por nó e adaptadores separados por transporte, todos convergindo para a mesma deduplicação/replay antes do domínio.

**Tech Stack:** C++20, CMake, CTest, TLS/mTLS, gRPC C++, HTTP(S), CI Windows/Linux.

**Spec:** `docs/implementation/2026-09-04-atlas-a6-transporte-multiprotocolo-design.md`

## Global Constraints

- Base obrigatória: `origin/main` em `52e804cffa321ed76bf76c8dcfc49029d29e1137`.
- Nenhum secret/certificado privado versionado.
- Nenhum shell, diagnóstico ativo, controle remoto ou LLM em A6.
- Todo buffer, payload, fila, batch, retry e replay deve ser bounded.
- Identidade autenticada limita nós/projetos representáveis; mensagem não amplia autoridade.
- Windows x64 e Linux x64 são plataformas obrigatórias.

---### Task 1: A6.1 Envelope remoto e sessão bounded

**Files:**
- Create: `infrastructure/node-agent/include/atlas/node_agent/remote_envelope.hpp`
- Create: `infrastructure/node-agent/src/remote_envelope.cpp`
- Create: `infrastructure/node-agent/include/atlas/node_agent/session_guard.hpp`
- Create: `infrastructure/node-agent/src/session_guard.cpp`
- Test: `infrastructure/node-agent/tests/remote_contract_tests.cpp`
- Modify: `infrastructure/node-agent/CMakeLists.txt`

**Interfaces:**
- Produces: `RemoteEnvelope`, `RemotePolicy`, `RemoteParseResult`, `parse_remote_envelope`, `SessionGuard::accept`.
- Consumes: `Severity` e `retry_delay` da A5.

- [ ] Escrever testes RED para versão, bounds, identidade nó→projeto, geração, sequência monotônica, replay e deduplicação cross-channel.
- [ ] Executar somente `remote_contract_tests` e observar falha pela ausência da API.
- [ ] Implementar o mínimo para GREEN sem sockets/TLS.
- [ ] Executar CTest completo e 150 testes Python.
- [ ] Commitar `feat(atlas): adicionar contratos remotos A6`.
### Task 2: A6.2 Canal vital TCP/mTLS

**Files:**
- Create: `infrastructure/node-agent/include/atlas/node_agent/vital_transport.hpp`
- Create: `infrastructure/node-agent/src/vital_transport.cpp`
- Test: `infrastructure/node-agent/tests/vital_transport_tests.cpp`
- Modify: `infrastructure/node-agent/CMakeLists.txt`

**Interfaces:**
- Consumes: `RemoteEnvelope`, `SessionGuard`, política de identidade.
- Produces: cliente/servidor vital com frame bounded e autenticação mTLS obrigatória.

- [ ] Selecionar e fixar a dependência TLS multiplataforma no CMake.
- [ ] Escrever teste RED de handshake mTLS, rejeição de CA/identidade incorreta e frame excessivo.
- [ ] Implementar TCP/TLS real com timeouts e sem thread/fila ilimitada.
- [ ] Certificar reconnect e entrega de crítico/recuperação.
- [ ] Commitar `feat(atlas): implementar canal vital mtls A6`.

### Task 3: A6.3 gRPC streaming/mTLS

- [ ] Fixar gRPC/Protobuf de forma reproduzível no build.
- [ ] Definir proto versionado apenas para envelopes/lotes pequenos.
- [ ] RED: streaming, identidade, dedupe e reconnect bounded.
- [ ] GREEN: cliente/servidor gRPC real com mTLS.
- [ ] Commitar `feat(atlas): implementar streaming grpc mtls A6`.
### Task 4: A6.4 HTTPS/mTLS

- [ ] Fixar cliente/servidor HTTPS reproduzível no build.
- [ ] RED: bootstrap/config/capabilities, mTLS, payload bounds e verbos/rotas permitidos.
- [ ] GREEN: HTTPS real sem endpoint de shell/controle destrutivo.
- [ ] Certificar sincronização bounded de pendências.
- [ ] Commitar `feat(atlas): implementar canal https mtls A6`.

### Task 5: A6.5 Roteamento e certificação

- [ ] RED: crítico usa canal vital e enriquecimento gRPC sem impacto duplicado.
- [ ] Integrar roteador com filas bounded e backoff A5.
- [ ] Testar falha parcial de canal, reconnect, replay, ordering e storm.
- [ ] Atualizar CI Windows/Linux para dependências e testes A6.
- [ ] Executar `git diff --check`, CTest, Python e instalação staging.
- [ ] Abrir PR Draft sobre `main`, aguardar todos gates GREEN no HEAD exato e registrar `/checkpoint`.

## Definition of Done A6

A6 termina apenas com os três transportes reais autenticados, política nó→projeto, sessão/replay/idempotência comuns, bounds observáveis e CI Windows/Linux GREEN no mesmo SHA. A7 não começa sobre A6 pending/RED.