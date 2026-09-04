# Atlas Node Agent A5 — Plano de Implementação

## Objetivo
Implementar o Agente de Nó Atlas em C++ multiplataforma para Windows x64 e Linux x64, responsável por coletar sinais vitais do host e receber eventos semânticos locais de projetos sem abrir portas de rede próprias.

## Base e limites
- Base certificada: A4 `e9b6eb236cdccb46c5ce203af4f54bc528e97604`.
- C++20, CMake e somente biblioteca padrão + APIs nativas do SO.
- A5 não implementa TCP/TLS, gRPC, HTTPS ou mTLS; isso pertence à A6.
- A5 não executa ping, traceroute, SSH nem ações de controle; isso pertence à A7.
- Nenhuma LLM, shell arbitrário, segredo ou instalação persistente.
- Filas, mensagens, payloads e históricos são bounded.

## Contrato local
O protocolo local é versionado e delimitado por linha: `ATLAS/1|project_id|event_id|event_type|severity|payload`.
Campos não podem conter `|`, CR ou LF; payload possui limite configurado. `project_id` e `event_type` são validados por política local versionada.
## Tarefas
1. Contratos C++ do evento local, política de projeto e fila priorizada bounded.
2. Coleta de sinais vitais com interface injetável e implementações Windows/Linux.
3. Bridge local: Named Pipe no Windows e Unix Socket no Linux, sem transporte externo.
4. Runtime do agente: ingestão validada -> fila -> snapshot/eventos prontos para futura A6.
5. CMake/CTest, smoke do binário e testes determinísticos.
6. CI Windows+Linux no HEAD exato, documentação, PR Draft e `/checkpoint`.

## DoD A5
- build C++20 em Windows x64 e Linux x64;
- testes unitários e integração locais PASS;
- fila permanece bounded sob storm e prioriza crítico/recuperação;
- payload/tipo/projeto/versão inválidos são rejeitados;
- sinais vitais são coletados sem thresholds universais inventados;
- bridge usa somente IPC local;
- nenhuma porta TCP/UDP é aberta;
- Foundation CI e Node Agent CI GREEN no mesmo HEAD.
