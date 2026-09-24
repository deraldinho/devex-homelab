# Runbook Operacional — Observabilidade e Diagnóstico do L2jToren

Este runbook orienta a operação, diagnóstico e resolução de incidentes no ecossistema **L2jToren** através do tecido sensorial do **Atlas**.

---

## 1. Topologia do Ecossistema no Host x99 (`100.101.23.111`)

O servidor de jogo e suas dependências de banco de dados e telemetria rodam conteinerizados na máquina Windows x99:

| Serviço | Porta | Tipo de Sonda | Impacto se Inativo |
|---|---|---|---|
| **GameServer** | `7777` TCP | Socket TCP connect | **Crítico**: Jogadores desconectados |
| **GameServer API** | `8088` HTTP | Socket TCP connect | Operacional: Painéis administrativos |
| **LoginServer** | `2106` TCP | Socket TCP connect | **Crítico**: Impossível autenticar na conta |
| **MariaDB** | `3306` TCP | Socket TCP connect | **Crítico**: Corrupção ou parada total |
| **Prometheus** | `9090` HTTP | Socket TCP connect + HTTP query | Observabilidade: Métricas e alertas |
| **Grafana** | `3000` HTTP | Socket TCP connect | Visualização: Dashboards de performance |
| **OpenTelemetry** | `4317` / `4318` | Docker status | Tracing distribuído |
| **Jaeger** | `16686` | Docker status | Análise de traces e gargalos de queries |

---

## 2. Como o Atlas Observa o L2jToren

A observação opera em modelo **híbrido**:
1. **Background Polling**: As sondas TCP verificam periodicamente se os serviços vitais respondem na rede Tailscale (`100.101.23.111`).
2. **Flash Query Sob Demanda (< 1.5s)**: Quando o operador envia uma pergunta ou comando no console do Discord (`#⚙️│bot-console`), o Atlas executa uma inspeção rápida via SSH utilizando as credenciais `~/.ssh/id_ed25519_x99_control` e formato PowerShell tipado:
   ```powershell
   docker ps --filter "name=l2jtoren" --format "{{.Names}}:::{{.Status}}:::{{.Image}}"
   ```
3. **Capabilities de Diagnóstico Registradas**:
   - `l2j_get_status`: Diagnóstico consolidado (portas + containers + heap da JVM + CPU + threads + conexões de banco).
   - `l2j_get_dashboards`: Consulta autenticada na API do Grafana (`100.101.23.111:3000`) listando os 6 dashboards oficiais:
     1. `l2j-autofarm-geo` (AutoFarm, Pickup & GeoEngine)
     2. `l2j-capacity-10k` (Capacity 10k)
     3. `l2j-economy-audit` (Economic Audit & Durability)
     4. `l2j-runtime-db` (JVM, ThreadPool & Database)
     5. `l2j-opcodes` (Opcodes & Packet Telemetry)
     6. `l2j-overview` (Overview, Login & Network)
   - `l2j_probe_ports`: Varredura das 6 portas de rede.
   - `l2j_docker_stats`: Estado de execução dos 7 containers.
   - `l2j_get_logs`: Extração direta das últimas linhas de log dos containers Docker (`l2jtoren-gameserver`, `l2jtoren-loginserver`, `l2jtoren-db`, etc.) via SSH com timeout estrito de 3.0s e sanitização de segurança.
   - `l2j_check_jvm`: Telemetria de heap e threads via Prometheus (`l2j_jvm_memory_heap_used_bytes`, `l2j_process_cpu_load`, etc.).

---

## 3. Interação pelo Discord

### No canal `#⚙️│bot-console` (`1473703295611568213`)
O operador pode dialogar normalmente com o Atlas em linguagem natural:
- *"Atlas, qual o status do ecossistema L2jToren?"*
- *"Como está a saúde do nosso servidor de jogo hoje?"*
- *"Atlas, extraia os logs recentes do gameserver"*
- *"Houve alguma queda de container no nó x99 recentemente?"*

O Atlas aciona as capabilities determinísticas e responde expressando o estado dos serviços como parte da integridade dos seus membros físicos.

### No canal `#🤖│watchdog` (`1476441917020700773`)
Alertas automáticos proativos são disparados caso:
1. Qualquer porta crítica (`7777`, `2106`, `3306`) caia ou fique inacessível.
2. Um container mude de status `Up` para `Exited` ou sofra crash.
3. A taxa de ocupação da JVM Heap ultrapasse o limiar operacional de **90.0%** (indicador de risco iminente de `OutOfMemoryError` ou degradação de GC).

---

## 4. Troubleshooting de Incidentes

### Caso 1: SSH Não Conecta ao x99 (`ssh_available: false`)
1. Verifique se o x99 está ligado e conectado na Tailscale:
   ```bash
   ping 100.101.23.111
   ```
2. Verifique o serviço OpenSSH Server no Windows x99:
   - Abra PowerShell como Administrador no Windows x99 e execute:
     ```powershell
     Get-Service sshd
     Start-Service sshd
     ```
3. Teste a chave SSH a partir do Pentium:
   ```bash
   ssh -i ~/.ssh/id_ed25519_x99_control deral@100.101.23.111 "docker ps"
   ```

### Caso 2: GameServer Porta 7777 DOWN, mas Docker Status UP
1. O processo Java pode estar em deadlock de inicialização ou estourado na JVM.
2. Inspecione os logs do container diretamente no x99:
   ```powershell
   docker logs --tail 100 l2jtoren-gameserver
   ```
3. Verifique se o MariaDB está aceitando conexões:
   ```powershell
   docker exec -it l2jtoren-db mariadb-admin -u root -p ping
   ```

### Caso 3: Reinício Emergencial de Serviços
Como medida de segurança e política de risco, comandos de reinício ou parada não são executados autonomamente pelo Atlas sem confirmação do operador (`requer_confirmacao: true`).
Para reiniciar manualmente os containers no x99:
```powershell
docker restart l2jtoren-gameserver l2jtoren-loginserver
```
