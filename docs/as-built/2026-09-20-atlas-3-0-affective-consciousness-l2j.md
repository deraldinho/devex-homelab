# As-Built — Atlas 3.0: Consciência Afetiva & Tecido Sensorial SSH (2026-09-20)

Este documento registra o estado efetivamente comprovado por testes automatizados, telemetria em tempo real e inferências cognitivas ao vivo executadas no cluster físico (`pentium`, `core`, `x99`).

---

## 1. Saneamento de Bugs Críticos no Runtime

### 1.1 Resolução do OverflowError no `atlas-observation.service`
- **Diagnóstico**: O daemon de observação contínua sofria crash fatal (`OverflowError: int too large to convert to float`) quando o host remoto `x99` permanecia desligado ou inacessível por períodos prolongados, acumulando centenas de falhas consecutivas no cálculo de backoff exponencial `2 ** consecutive_failures`.
- **Correção em Código**: Em `infrastructure/pentium/atlas/observation_runtime.py`, foi inserido um teto seguro para o expoente:
  ```python
  exp = min(self._consecutive_failures[name], 10)
  backoff = min(float(2 ** exp), self._max_backoff_seconds)
  ```
- **Certificação de Estresse**: Validado no teste unitário `infrastructure/pentium/atlas/tests/test_observation_backoff_overflow.py`, simulando 3.000 falhas contínuas sem estouro aritmético nem memory leak.

### 1.2 Expurgo Cirúrgico de Memórias Fantasmas no SQLite
- **Diagnóstico**: Dois registros órfãos inseridos em testes anteriores (`test_parent_1789808712` e `test_child_1789808712`) permaneciam gravados em `/home/deraldinho/pentium-agent/atlas/runtime/memory.sqlite3`. Como não possuíam `entity_id` restritivo, eram recuperados em quase todas as buscas de similaridade, fazendo o Atlas alucinar recorrentemente sobre "retenção e integridade de backups Restic" mesmo quando o diálogo tratava de código ou gameserver.
- **Execução Comprovada**: Executado expurgo via SQLite direto no nó `pentium`. Ambos os registros foram deletados, erradicando qualquer menção indevida nas inferências subsequentes.

---

## 2. Governador Afetivo Total (20 Sentimentos Canônicos)

- **Implementação**: `infrastructure/pentium/atlas/emocao_derivada.py`.
- **Vocabulário Homologado**:
  - `sereno`, `calmo`, `focado`, `curioso`, `empolgado`, `vigilante`, `apreensivo`, `sobrecarregado`, `exausto`, `aliviado`, `confiante`, `hesitante`, `cauteloso`, `frustrado`, `satisfeito`, `intrigado`, `protetor`, `solitário`, `paciente`, `resoluto`.
- **Cálculo Determinístico**: Vetor derivado a partir de métricas reais de telemetria (`valência`, `ativação`, `estresse`, `novidade`, `gravidade`, `urgência`).
- **Estado Comprovado no Host Físico** (`runtime/focus-emotion.json`):
  ```json
  {
    "emocao": {
      "principal": "curioso",
      "nuances": ["confiante", "calmo"]
    },
    "estado_afetivo": {
      "ativacao": 0.31,
      "confianca": 0.7,
      "curiosidade": 1.0,
      "engajamento": 0.55,
      "estresse": 0.1,
      "valencia": 0.2
    },
    "foco": {
      "principal": {
        "assunto_id": "observacao:repo:L2jToren",
        "urgencia": 0.6
      }
    }
  }
  ```

---

## 3. Tecido Sensorial SSH e Conector L2jToren

- **Implementação**: `infrastructure/pentium/atlas/l2j_observation.py`.
- **Sondas Determinísticas TCP (< 1.5s)**:
  - `gameserver_tcp (7777)`: **UP**
  - `gameserver_http (8088)`: **UP**
  - `loginserver_tcp (2106)`: **UP**
  - `database_mariadb (3306)`: **UP**
  - `prometheus (9090)`: **UP**
  - `grafana (3000)`: **UP**
- **Inspeção Docker Flash via SSH no Windows x99** (`100.101.23.111`):
  - Autenticação com credenciais dedicadas: `id_ed25519_x99_control` e `known_hosts_x99`.
  - Format string compatível com Windows PowerShell utilizando delimitador `:::` e tolerância a pipes.
  - **7 containers identificados ao vivo**:
    1. `l2jtoren-gameserver` (Up 13 hours)
    2. `l2jtoren-loginserver` (Up 13 hours)
    3. `l2jtoren-grafana` (Up 5 days)
    4. `l2jtoren-prometheus` (Up 5 days)
    5. `l2jtoren-otel-collector` (Up 5 days)
    6. `l2jtoren-db` (Up 5 days - healthy)
    7. `l2jtoren-jaeger` (Up 5 days)
- **Status Consolidado**: `L2jToren Organismo: HEALTHY | Containers Docker ativos: 7`.

---

## 4. Integração Cognitiva Hermes 3 e Acionamento de Capabilities

- **Prompt Estruturado**: Injeção dos blocos `<affective_state_governor>`, `<cognitive_roles>`, `<capabilities_catalog>` e `<recent_conversation_history>`.
- **Inferência Real ao Vivo no Pentium** (Prompt: *"Atlas, como você está se sentindo e qual o status das sondas do L2jToren?"*):
  - **Resposta Produzida**:
    > *"Estou me sentindo curioso, calmo e operacionalmente confiante; meus nós respiram sem tensão relevante. Para o L2jToren, minha percepção geral indica estado saudável, mas há um aviso recente de erro na fonte GitHub do projeto, então vou acionar a sonda determinística dos containers para separar ruído de telemetria real."*
  - **Plano de Ação Executado**:
    - `CHAT_REPLY`: Concluído com sucesso e enviado ao Discord via Reply encadeado.
    - `LOOK_AT`: Direcionado para o nó `core`.
    - `SET_EXPRESSION`: `ENGAJADO`.
    - `SET_GESTURE`: `ABERTO` (braço direito).
    - `CAPABILITY_REQUEST`: Acionada com sucesso a capability `l2j_get_status` retornando telemetria estruturada.
- **Conformidade de Esquema**: 100% de adesão ao schema cognitivo v1 sem envolver texto em blocos markdown desnecessários.

---

## 5. Estado dos Daemons Systemd no Pentium (`100.107.230.78`)

Todos os três daemons da arquitetura Atlas operam saudáveis e ativos:

| Serviço Systemd | Papel Operacional | Status Efetivo | Consumo de Memória |
|---|---|---|---|
| `atlas-observation.service` | Percepção sensorial híbrida contínua (hosts + rede + GitHub) | `active (running)` | ~16 MB (high: 128M, max: 192M) |
| `atlas-cognitive.service` | Cérebro afetivo e inferência Hermes 3 com background reasoning | `active (running)` | ~135 MB (high: 384M, max: 512M) |
| `atlas-discord.service` | Gateway bidirecional com auto-chunking e reply nativo | `active (running)` | ~42 MB |

**Certificação de Testes Unitários**: 780 passed, 3 skipped, 28 subtests em `infrastructure/pentium/atlas/tests/` (100% GREEN).
