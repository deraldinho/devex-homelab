# As-Built — Homelab Stabilization & Master Gap Closure (2026-09-19)

Este documento registra o estado efetivamente comprovado por testes automatizados e builds após a execução do plano mestre de fechamento de lacunas operacionais.

---

## 1. Capacity & Security dos Runners no Core (Issues #12 e #13)

- Manifestos atualizados em `infrastructure/core/runners/compose.yaml`.
- **Limites de cgroups (CPU e Memória)**:
  - `core-l2jtoren-01`: `cpus: "3.0"`, `memory: 3500M` (workload heavy).
  - `core-l2jtoren-02`: `cpus: "2.0"`, `memory: 2000M` (workload normal).
  - `core-homelab-01`: `cpus: "1.5"`, `memory: 1000M` (CI do DevEx HomeLab).
  - **Soma total de memória**: 6500 MB (garante margem segura dentro dos 7.1 GiB físicos do Core).
- **Hardening de Segurança**:
  - Diretiva `security_opt: ["no-new-privileges:true"]` aplicada aos 3 serviços.
  - Volumes de trabalho `_work` totalmente isolados por instância e projeto.
- **Healthcheck Determinístico**:
  - `CMD-SHELL pgrep -f Runner.Listener >/dev/null || exit 1`.
- **Certificação**: Testes unitários em `infrastructure/core/tests/test_runner_capacity.py` (5/5 PASS).

---

## 2. Observabilidade & Detector de Drift (Issue #10)

- Implementados `infrastructure/observability/drift_model.py` e `infrastructure/observability/drift_detector.py`.
- Compara `DesiredComponent` (definido pelo Git) contra `ObservedComponent` (retornado pelos nós).
- Classificação determinística:
  - `CLEAN`: concordância total.
  - `WARNING`: divergência de tag/imagem ou versão menor.
  - `CRITICAL`: ausência de componente obrigatório ou estado de execução divergente (`exited` vs `running`).
- **Certificação**: Testes unitários em `infrastructure/observability/tests/test_drift_detector.py` (5/5 PASS).

---

## 3. Backup & Disaster Recovery com GitHub Releases Vault (Issue #11)

- Implementados:
  - `infrastructure/backup/compose.yaml`: Restic conteinerizado com montagem `:ro`.
  - `infrastructure/backup/restic-backup.sh`: Snapshot com tags, auto-unlock, pré-hook transacional SQLite (`.backup`) e alertas Discord.
  - `infrastructure/backup/github-sync.sh`: Criptografia AES-256-CBC com PBKDF2 (100k iterações), manifesto `SHA256SUMS.txt`, 3 retries com backoff, upload para GitHub Releases privadas e expurgo automático retendo as 14 releases mais recentes.
  - `infrastructure/backup/systemd/`: Service e timer diários às 03:00 com random delay.
- **Integração com Heartbeat**: `infrastructure/pentium/heartbeat/heartbeat.py` monitora `/state/backup_status.json`, degradando o nó se o backup falhar ou tiver mais de 26h.
- **Certificação**: Testes unitários em `infrastructure/backup/tests/test_backup_contract.py` (9/9 PASS).

---

## 4. Biblioteca e Assets de Áudio do Atlas

- Implementado `infrastructure/pentium/atlas/audio/generate_tone_assets.py`.
- 10 categorias canônicas sintetizadas em PCM 16-bit 44.1kHz mono:
  - `calm`, `acknowledge`, `working`, `happy`, `concerned`, `annoyed`, `critical`, `relief`, `confused`, `victory`.
- Salvos em `infrastructure/pentium/atlas/assets/audio/<category>/tone_01.wav`.
- **Certificação**: Testes unitários em `infrastructure/pentium/atlas/audio/tests/test_audio_assets.py` (1/1 PASS).

---

## 5. Simulação Local na x99 (`dev/simulation`)

- `dev/simulation/compose.yaml` atualizado com limites cgroups equivalentes ao Pentium (512M) e Core (1500M).
- `dev/simulation/verify.sh` integrado com asserção do detector de drift executando dentro do container `sim-pentium`.

---

## 6. Saneamento e Capacity Físico no Host Core (Comprovado ao Vivo)

- **Recuperação de Espaço em Disco**: Expurgo de 100+ GB de camadas e caches acumulados de builds passados; partição `/` reduziu de **93% de ocupação (18 GB livres)** para **63% de ocupação (88 GB livres)**.
- **Prevenção Automatizada**: Criada rotina diária no systemd do Core (`docker-cleanup.timer`) executando expurgo diário às 04:00.
- **Enforcement de Capacity nos Runners**:
  - `core-homelab-01`: 1.5 CPUs, 1000M RAM.
  - `core-l2jtoren-01`: 3.0 CPUs, 3500M RAM.
  - `core-l2jtoren-02`: 2.0 CPUs, 2000M RAM.
- **Auditoria de Drift ao Vivo**: Executado [`infrastructure/observability/cli_drift_audit.py`](file:///c:/Users/deral/DevEx-HomeLab/infrastructure/observability/cli_drift_audit.py) em tempo real via SSH contra o cluster físico:
  - **Status Global: `CLEAN`** (7/7 componentes em perfeita paridade com o Git).
