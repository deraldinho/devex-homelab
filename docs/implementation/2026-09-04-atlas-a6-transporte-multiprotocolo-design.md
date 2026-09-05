# Atlas A6 — Transporte Multiprotocolo

## Objetivo

Implementar os três canais remotos aprovados para o Agente de Nó Atlas sem alterar o contrato A5 de IPC local e sem introduzir diagnóstico ativo ou LLM.

A6 transporta eventos já validados pelo A5. Ela não decide saúde técnica, estado afetivo, foco ou reação.

## Canais

1. TCP + TLS/mTLS: canal vital para heartbeat, crítico, recuperação e sinais físicos essenciais.
2. gRPC streaming + mTLS: canal operacional principal para eventos de projeto e lotes pequenos.
3. HTTPS + mTLS: bootstrap, sincronização, capacidades, identidade e configuração não destrutiva.

Os três canais compartilham o mesmo envelope lógico e a mesma política de identidade/idempotência.
## Envelope e sessão

Cada mensagem remota contém `protocol_version`, `node_id`, `project_id`, `event_id`, `event_type`, `severity`, `session_generation`, `sequence`, `occurred_at` e payload bounded.

`session_generation` muda a cada nova sessão autenticada do agente. `sequence` é monotônica dentro da geração. O receptor mantém janela limitada de replay por `(node_id, generation)` e deduplica globalmente por `event_id` dentro de retenção bounded.

A identidade do certificado autenticado é mapeada para `node_id`; a política do nó define quais `project_id` ele pode representar. O conteúdo da mensagem nunca pode ampliar essa autoridade.

## Segurança

Todo canal remoto exige TLS. Produção exige autenticação mútua. Certificados, chaves e trust stores são configuração externa e nunca entram no repositório.

A6 não executa shell, não altera rede, não reinicia serviços e não recebe ações destrutivas. HTTPS aceita apenas operações administrativas explicitamente tipadas e não destrutivas.

Payload, frame, batch, fila, janela de replay, concorrência e retry são limitados por configuração.
## Fluxo de entrega

A fila A5 entrega `LocalEvent` ao roteador A6. Eventos `critical` e `recovery` podem usar TCP vital imediatamente e posteriormente aparecer no stream gRPC para enriquecimento; o receptor aplica idempotência antes de qualquer efeito de domínio.

Eventos operacionais normais seguem gRPC streaming. HTTPS é reservado para bootstrap/sync/configuração e não é fallback silencioso para tráfego ilimitado.

Retry usa backoff exponencial bounded já introduzido em A5, com jitter determinístico/injetável nos testes. Nenhum canal mantém fila própria ilimitada.

## Falhas

Falha de um canal não redefine saúde do nó. A indisponibilidade de transporte produz evidência de percepção degradada e pode permitir outro canal somente quando a política daquele tipo de mensagem autorizar.

Mensagens com versão desconhecida, nó não autorizado, projeto não autorizado, sequência repetida/antiga fora da janela, frame excessivo ou payload inválido são recusadas sem encaminhamento.

## Certificação

A6.1 certifica contratos, sessão, replay e roteamento sem rede. A6.2 certifica TCP/mTLS real. A6.3 certifica gRPC streaming/mTLS real. A6.4 certifica HTTPS/mTLS real. A6.5 executa integração Windows/Linux, reconnect, duplicação cross-channel, bounds e CI no HEAD exato.
## Dependência TLS A6.2

O canal vital usa Mbed TLS 3.6.7 LTS, obtido exclusivamente do release oficial e fixado por SHA-256 `a7e8bcbec0e6f761b4af24f25677626b35f762f68eef79c08677a363212d11f6` via CMake FetchContent. Certificados de teste são gerados de forma efêmera no diretório de build; nenhuma chave privada ou certificado operacional é versionado.

## Dependência gRPC A6.3

O gRPC C++ e Protobuf são consumidos por manifest vcpkg. O snapshot autoritativo do registry é o commit `04a9d8e5212d01ee1dd9478eadd9caade4f8b0d4`, no qual o port `grpc` é `1.81.1`.

O repositório não clona gRPC nem seus submódulos durante o CMake. O CI faz checkout explícito do commit vcpkg acima, executa o bootstrap e entrega o toolchain ao CMake. Isso evita gitlinks flutuantes e mantém Windows/Linux no mesmo grafo de ports.

O streaming gRPC autentica cliente e servidor por mTLS, limita lote e payload e preserva integralmente o `RemoteEnvelope`. Política de projeto, replay e deduplicação cross-channel continuam no ingress comum A6.5, para não manter estado divergente por transporte.

Para os gates de CI, os overlay triplets `x64-linux-release` e `x64-windows-release` mantêm os mesmos vínculos de CRT/biblioteca dos triplets oficiais pinados e acrescentam apenas `VCPKG_BUILD_TYPE=release`. O workflow aplica o mesmo triplet a `VCPKG_TARGET_TRIPLET` e `VCPKG_HOST_TRIPLET`, evitando que ferramentas de host voltem ao triplet nativo padrão e reconstruam um segundo grafo Debug+Release. Assim o gate compila apenas os artefatos Release que participam da certificação.
