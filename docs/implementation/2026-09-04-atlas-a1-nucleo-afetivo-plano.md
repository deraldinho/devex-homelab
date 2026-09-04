# Plano de Implementação — Atlas A1 Núcleo Afetivo

> **Para agentes de implementação:** SUB-SKILL OBRIGATÓRIA: usar `superpowers:subagent-driven-development` (recomendado) ou `superpowers:executing-plans` para executar este plano tarefa por tarefa. Os passos usam caixas `- [ ]` para acompanhamento.

**Objetivo:** implementar o núcleo afetivo determinístico e persistente do Atlas, com personalidade-base, seis dimensões afetivas, impulsos limitados, decaimento temporal e retomada segura após reinício, sem LLM, rede nova ou controle remoto.

**Arquitetura:** A1 introduz contratos puros em Python, separados do `state_model.py` técnico já certificado. `modelo_afetivo.py` define dados e invariantes; `configuracao_afetiva.py` carrega personalidade e política de decaimento; `motor_afetivo.py` aplica impulsos e decaimento; `persistencia_afetiva.py` salva/restaura snapshot atômico. A1 não seleciona foco por prioridade, não correlaciona incidentes e não interpreta entidades; essas responsabilidades permanecem para A2–A4.

**Stack técnica:** Python 3 da stack atual, `dataclasses`, `enum`, `datetime`, `json`, `pathlib`, `os`, `unittest`; sem dependências externas.

**Especificação:** `docs/implementation/2026-09-04-atlas-motor-estado-afetivo-design.md`

## Restrições globais

- Base obrigatória: `atlas/issue-20-observation-runtime` no SHA `1a28a54a051d152d83cf919a7f570e1bacccdf2e`.
- Novos contratos, documentação, testes e mensagens de gate em português do Brasil; identificadores Python novos em português sem acentos.
- `TechnicalState`, `Stimulus`, `ObservationRuntime` e demais contratos certificados anteriores não serão renomeados nesta slice.
- Estado técnico continua autoritativo e A1 não possui API capaz de alterá-lo.
- Zero chamadas de LLM, TTS, STT, áudio ou memes.
- Zero alteração de rede, SSH, Tailscale, firewall, modem, DNS ou rotas.
- Zero shell arbitrário e zero ação CONTROL/DESTRUCTIVE.
- Nenhum novo serviço persistente será instalado ou ativado fisicamente nesta slice.
- Todos os valores afetivos permanecem bounded.
- Relógio de testes é explícito/injetável; nenhum teste depende de `sleep()`.
- TDD obrigatório: RED observável antes de cada implementação de produção.
- Cada tarefa termina em commit pequeno e revisável.

## Estrutura de arquivos

### Criar

- `infrastructure/pentium/atlas/modelo_afetivo.py` — contratos `EstadoAfetivo`, `PersonalidadeBase`, `PoliticaDecaimento`, `ImpulsoAfetivo` e `EstadoConsciencia`.
- `infrastructure/pentium/atlas/configuracao_afetiva.py` — loader estrito da configuração afetiva schema v1.
- `infrastructure/pentium/atlas/config_afetiva.json` — personalidade-base inicial e meias-vidas calibráveis.
- `infrastructure/pentium/atlas/motor_afetivo.py` — aplicação de impulso, decaimento online e atenuação offline limitada.
- `infrastructure/pentium/atlas/persistencia_afetiva.py` — snapshot JSON atômico, carga estrita e restauração segura.
- `infrastructure/pentium/atlas/tests/test_modelo_afetivo.py` — invariantes, bounds, freeze e serialização.
- `infrastructure/pentium/atlas/tests/test_configuracao_afetiva.py` — schema, valores iniciais e rejeições.
- `infrastructure/pentium/atlas/tests/test_motor_afetivo.py` — impulso, meia-vida, timestamp e atenuação offline.
- `infrastructure/pentium/atlas/tests/test_persistencia_afetiva.py` — escrita atômica, reload, corrupção e fallback.
- `infrastructure/pentium/atlas/tests/test_nucleo_afetivo_empacotamento.py` — installer e CI incluem A1 sem habilitar serviço persistente.

### Modificar

- `infrastructure/pentium/atlas/install-user.sh` — empacotar/compilar A1 e validar `config_afetiva.json`, sem `systemctl enable/start`.
- `.github/workflows/foundation-ci.yml` — adicionar módulos A1 ao `py_compile`, validar JSON e emitir marker A1.
- `docs/as-built/2026-09-02-baseline.md` — registrar somente evidência realmente obtida no HEAD final da A1.

---

### Tarefa 1: Contratos e invariantes do modelo afetivo

**Arquivos:**
- Criar: `infrastructure/pentium/atlas/modelo_afetivo.py`
- Criar: `infrastructure/pentium/atlas/tests/test_modelo_afetivo.py`

**Interfaces:**
- Consome: nenhum contrato novo; apenas biblioteca padrão.
- Produz:
  - `EstadoConsciencia(str, Enum)` com valores `ativo`, `degradado`, `isolado`, `retomando`;
  - `PersonalidadeBase(valencia, ativacao, estresse, confianca, engajamento, curiosidade)`;
  - `PoliticaDecaimento(meia_vida_valencia_s, meia_vida_ativacao_s, meia_vida_estresse_s, meia_vida_confianca_s, meia_vida_engajamento_s, meia_vida_curiosidade_s, limite_atenuacao_offline_s)`;
  - `EstadoAfetivo(valencia, ativacao, estresse, confianca, engajamento, curiosidade, foco_atencao, estado_consciencia, atualizado_em)`;
  - `ImpulsoAfetivo(tipo, motivo, delta_valencia, delta_ativacao, delta_estresse, delta_confianca, delta_engajamento, delta_curiosidade)`.

- [ ] **Passo 1: escrever teste RED para enum, bounds, freeze e serialização**

Criar `test_modelo_afetivo.py` com testes equivalentes a:

```python
import dataclasses
import json
import unittest

from infrastructure.pentium.atlas.modelo_afetivo import (
    EstadoAfetivo,
    EstadoConsciencia,
    ImpulsoAfetivo,
    PersonalidadeBase,
    PoliticaDecaimento,
)


class ModeloAfetivoTests(unittest.TestCase):
    def test_estado_consciencia_tem_contrato_estavel(self):
        self.assertEqual(
            [item.value for item in EstadoConsciencia],
            ["ativo", "degradado", "isolado", "retomando"],
        )

    def test_estado_e_personalidade_limitam_dimensoes(self):
        personalidade = PersonalidadeBase(2.0, -1.0, 2.0, -1.0, 2.0, -1.0)
        estado = EstadoAfetivo(
            valencia=-2.0,
            ativacao=2.0,
            estresse=-1.0,
            confianca=2.0,
            engajamento=-1.0,
            curiosidade=2.0,
            foco_atencao=None,
            estado_consciencia=EstadoConsciencia.RETOMANDO,
            atualizado_em="2026-09-04T15:00:00+00:00",
        )
        self.assertEqual(personalidade.valencia, 1.0)
        self.assertEqual(personalidade.ativacao, 0.0)
        self.assertEqual(estado.valencia, -1.0)
        self.assertEqual(estado.ativacao, 1.0)
        self.assertEqual(estado.estresse, 0.0)
        self.assertEqual(estado.confianca, 1.0)

    def test_impulso_limita_deltas_em_menos_um_mais_um(self):
        impulso = ImpulsoAfetivo("teste", "teste", -4, 4, -4, 4, -4, 4)
        self.assertEqual(impulso.delta_valencia, -1.0)
        self.assertEqual(impulso.delta_ativacao, 1.0)

    def test_contratos_sao_imutaveis_e_serializaveis(self):
        estado = EstadoAfetivo(
            0.2, 0.3, 0.1, 0.7, 0.5, 0.75,
            None, EstadoConsciencia.RETOMANDO,
            "2026-09-04T15:00:00+00:00",
        )
        with self.assertRaises(dataclasses.FrozenInstanceError):
            estado.estresse = 0.8
        serializado = json.dumps(estado.to_dict(), ensure_ascii=False, sort_keys=True)
        self.assertIn('"estado_consciencia": "retomando"', serializado)
```

- [ ] **Passo 2: executar apenas o novo teste e confirmar RED**

Executar:

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_modelo_afetivo -v
```

Esperado: FAIL por `ModuleNotFoundError` para `modelo_afetivo`.

- [ ] **Passo 3: implementar o modelo mínimo**

Em `modelo_afetivo.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


def _limitar_01(valor: float) -> float:
    return max(0.0, min(1.0, float(valor)))


def _limitar_valencia(valor: float) -> float:
    return max(-1.0, min(1.0, float(valor)))


def _limitar_delta(valor: float) -> float:
    return max(-1.0, min(1.0, float(valor)))


class EstadoConsciencia(str, Enum):
    ATIVO = "ativo"
    DEGRADADO = "degradado"
    ISOLADO = "isolado"
    RETOMANDO = "retomando"
```

Completar as quatro `@dataclass(frozen=True)` aplicando clamps em `__post_init__`. `PoliticaDecaimento` deve rejeitar qualquer meia-vida `<= 0` e `limite_atenuacao_offline_s < 0` com `ValueError`. `EstadoAfetivo.to_dict()` e `ImpulsoAfetivo.to_dict()` devem usar nomes pt-BR e tipos JSON simples.

- [ ] **Passo 4: executar o teste do modelo até GREEN**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_modelo_afetivo -v
```

Esperado: PASS.

- [ ] **Passo 5: executar regressão Atlas existente**

```bash
python3 -m unittest discover -s infrastructure/pentium/atlas/tests -p 'test_*.py' -v
```

Esperado: 60 testes legados + novos testes A1, todos GREEN.

- [ ] **Passo 6: commit**

```bash
git add infrastructure/pentium/atlas/modelo_afetivo.py infrastructure/pentium/atlas/tests/test_modelo_afetivo.py
git commit -m "feat(atlas): adicionar contratos do estado afetivo"
```

---

### Tarefa 2: Configuração da personalidade-base e política de decaimento

**Arquivos:**
- Criar: `infrastructure/pentium/atlas/configuracao_afetiva.py`
- Criar: `infrastructure/pentium/atlas/config_afetiva.json`
- Criar: `infrastructure/pentium/atlas/tests/test_configuracao_afetiva.py`

**Interfaces:**
- Consome: `PersonalidadeBase`, `PoliticaDecaimento`.
- Produz: `carregar_configuracao_afetiva(path: Path) -> tuple[PersonalidadeBase, PoliticaDecaimento]`.

**Valores iniciais calibráveis aprovados para iniciar a A1:**

```json
{
  "versao_schema": 1,
  "personalidade_base": {
    "valencia": 0.20,
    "ativacao": 0.25,
    "estresse": 0.10,
    "confianca": 0.70,
    "engajamento": 0.50,
    "curiosidade": 0.75
  },
  "decaimento": {
    "meia_vida_segundos": {
      "valencia": 3600,
      "ativacao": 1200,
      "estresse": 1800,
      "confianca": 14400,
      "engajamento": 7200,
      "curiosidade": 10800
    },
    "limite_atenuacao_offline_segundos": 1800
  }
}
```

Esses números são configuração, não constante de domínio. Mantêm a relação aprovada: ativação/estresse recuperam mais rápido, valência em ritmo intermediário, confiança/engajamento/curiosidade mais lentamente.

- [ ] **Passo 1: escrever teste RED do loader e do arquivo real**

```python
import json
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.configuracao_afetiva import carregar_configuracao_afetiva

ROOT = Path(__file__).resolve().parents[4]
CONFIG = ROOT / "infrastructure" / "pentium" / "atlas" / "config_afetiva.json"


class ConfiguracaoAfetivaTests(unittest.TestCase):
    def test_configuracao_real_carrega_schema_um(self):
        personalidade, politica = carregar_configuracao_afetiva(CONFIG)
        self.assertEqual(personalidade.valencia, 0.20)
        self.assertEqual(personalidade.curiosidade, 0.75)
        self.assertEqual(politica.meia_vida_ativacao_s, 1200.0)
        self.assertEqual(politica.meia_vida_confianca_s, 14400.0)
        self.assertEqual(politica.limite_atenuacao_offline_s, 1800.0)

    def test_rejeita_schema_desconhecido(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "config.json"
            path.write_text(json.dumps({"versao_schema": 99}), encoding="utf-8")
            with self.assertRaises(ValueError):
                carregar_configuracao_afetiva(path)
```

Adicionar casos RED para campo obrigatório ausente e meia-vida inválida.

- [ ] **Passo 2: executar e confirmar RED**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_configuracao_afetiva -v
```

Esperado: FAIL por módulo/configuração ausente.

- [ ] **Passo 3: criar `config_afetiva.json` exatamente com o schema acima**

Validar manualmente:

```bash
python3 -m json.tool infrastructure/pentium/atlas/config_afetiva.json >/dev/null
```

Esperado: exit 0.

- [ ] **Passo 4: implementar loader estrito**

`configuracao_afetiva.py` deve:

```python
def carregar_configuracao_afetiva(path: Path) -> tuple[PersonalidadeBase, PoliticaDecaimento]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("versao_schema") != 1:
        raise ValueError("configuração afetiva versao_schema deve ser 1")
    # ler chaves obrigatórias explicitamente; KeyError vira ValueError com nome do campo
    # construir PersonalidadeBase e PoliticaDecaimento
```

Não aceitar defaults silenciosos para campos obrigatórios da A1.

- [ ] **Passo 5: executar testes A1 e regressão Atlas**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_configuracao_afetiva -v
python3 -m unittest discover -s infrastructure/pentium/atlas/tests -p 'test_*.py' -v
```

Esperado: GREEN.

- [ ] **Passo 6: commit**

```bash
git add infrastructure/pentium/atlas/configuracao_afetiva.py infrastructure/pentium/atlas/config_afetiva.json infrastructure/pentium/atlas/tests/test_configuracao_afetiva.py
git commit -m "feat(atlas): configurar personalidade e decaimento afetivo"
```

---

### Tarefa 3: Motor puro de impulso e decaimento temporal

**Arquivos:**
- Criar: `infrastructure/pentium/atlas/motor_afetivo.py`
- Criar: `infrastructure/pentium/atlas/tests/test_motor_afetivo.py`

**Interfaces:**
- Consome: `EstadoAfetivo`, `EstadoConsciencia`, `ImpulsoAfetivo`, `PersonalidadeBase`, `PoliticaDecaimento`.
- Produz:
  - `criar_estado_inicial(personalidade: PersonalidadeBase, atualizado_em: str) -> EstadoAfetivo`;
  - `aplicar_impulso(estado: EstadoAfetivo, impulso: ImpulsoAfetivo, atualizado_em: str) -> EstadoAfetivo`;
  - `decair_estado(estado: EstadoAfetivo, personalidade: PersonalidadeBase, politica: PoliticaDecaimento, atualizado_em: str) -> EstadoAfetivo`;
  - `atenuar_estado_offline(estado: EstadoAfetivo, personalidade: PersonalidadeBase, politica: PoliticaDecaimento, retomado_em: str) -> EstadoAfetivo`.

**Regra matemática:** para cada dimensão, retorno exponencial à linha de base:

```text
novo = base + (atual - base) * 0.5 ** (tempo_decorrido / meia_vida)
```

A função online usa todo o tempo decorrido. A função offline usa `min(tempo_decorrido, limite_atenuacao_offline_s)` e grava `atualizado_em=retomado_em`, impedindo que 12 horas desligado sejam tratadas como 12 horas conscientes.

- [ ] **Passo 1: escrever testes RED do estado inicial e aplicação de impulso**

```python
import unittest

from infrastructure.pentium.atlas.modelo_afetivo import (
    EstadoAfetivo,
    EstadoConsciencia,
    ImpulsoAfetivo,
    PersonalidadeBase,
    PoliticaDecaimento,
)
from infrastructure.pentium.atlas.motor_afetivo import aplicar_impulso, criar_estado_inicial


class MotorAfetivoTests(unittest.TestCase):
    def setUp(self):
        self.personalidade = PersonalidadeBase(0.2, 0.25, 0.1, 0.7, 0.5, 0.75)

    def test_estado_inicial_nasce_no_baseline_e_retomando(self):
        estado = criar_estado_inicial(self.personalidade, "2026-09-04T15:00:00+00:00")
        self.assertEqual(estado.valencia, 0.2)
        self.assertEqual(estado.estresse, 0.1)
        self.assertEqual(estado.estado_consciencia, EstadoConsciencia.RETOMANDO)

    def test_impulso_soma_e_limita_sem_alterar_foco(self):
        estado = criar_estado_inicial(self.personalidade, "2026-09-04T15:00:00+00:00")
        impulso = ImpulsoAfetivo("perda", "teste", -0.8, 0.9, 1.0, -0.8, 0.4, 0.1)
        novo = aplicar_impulso(estado, impulso, "2026-09-04T15:00:01+00:00")
        self.assertAlmostEqual(novo.valencia, -0.6)
        self.assertEqual(novo.ativacao, 1.0)
        self.assertEqual(novo.estresse, 1.0)
        self.assertEqual(novo.foco_atencao, estado.foco_atencao)
```

- [ ] **Passo 2: executar e confirmar RED**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_motor_afetivo -v
```

Esperado: FAIL por `motor_afetivo` ausente.

- [ ] **Passo 3: implementar criação inicial e aplicação mínima**

`criar_estado_inicial` copia as seis dimensões da personalidade, define `foco_atencao=None`, `estado_consciencia=RETOMANDO` e usa o timestamp recebido.

`aplicar_impulso` soma cada delta à dimensão correspondente; os clamps do `EstadoAfetivo` são a última barreira. Deve preservar `foco_atencao` e `estado_consciencia`, pois A1 ainda não decide foco nem consciência operacional.

- [ ] **Passo 4: executar os testes e confirmar GREEN parcial**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_motor_afetivo -v
```

Esperado: testes de criação/impulso PASS.

- [ ] **Passo 5: acrescentar testes RED para meia-vida e timestamp regressivo**

Adicionar:

```python
def test_decaimento_respeita_meia_vida_por_dimensao(self):
    politica = PoliticaDecaimento(3600, 1200, 1800, 14400, 7200, 10800, 1800)
    estado = EstadoAfetivo(
        1.0, 0.25, 0.9, 0.7, 0.5, 0.75,
        None, EstadoConsciencia.ATIVO,
        "2026-09-04T15:00:00+00:00",
    )
    novo = decair_estado(
        estado, self.personalidade, politica,
        "2026-09-04T16:00:00+00:00",
    )
    self.assertAlmostEqual(novo.valencia, 0.6, places=6)


def test_rejeita_tempo_regressivo(self):
    politica = PoliticaDecaimento(3600, 1200, 1800, 14400, 7200, 10800, 1800)
    estado = criar_estado_inicial(self.personalidade, "2026-09-04T15:00:00+00:00")
    with self.assertRaises(ValueError):
        decair_estado(estado, self.personalidade, politica, "2026-09-04T14:59:59+00:00")
```

- [ ] **Passo 6: executar e confirmar RED da função de decaimento**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_motor_afetivo -v
```

Esperado: FAIL por `decair_estado` ausente ou comportamento ainda não implementado.

- [ ] **Passo 7: implementar parsing de ISO-8601 aware e decaimento exponencial**

Usar `datetime.fromisoformat()`. Rejeitar timestamps sem `tzinfo`/offset e rejeitar tempo regressivo. Não usar `time.time()` dentro do motor.

- [ ] **Passo 8: acrescentar teste RED da atenuação offline limitada**

```python
def test_atenuacao_offline_aplica_no_maximo_limite_e_entra_retomando(self):
    politica = PoliticaDecaimento(3600, 1200, 1800, 14400, 7200, 10800, 1800)
    estado = EstadoAfetivo(
        0.2, 0.25, 0.9, 0.7, 0.5, 0.75,
        "x99", EstadoConsciencia.DEGRADADO,
        "2026-09-04T00:00:00+00:00",
    )
    novo = atenuar_estado_offline(
        estado, self.personalidade, politica,
        "2026-09-04T12:00:00+00:00",
    )
    self.assertAlmostEqual(novo.estresse, 0.5, places=6)
    self.assertEqual(novo.estado_consciencia, EstadoConsciencia.RETOMANDO)
    self.assertEqual(novo.foco_atencao, "x99")
    self.assertEqual(novo.atualizado_em, "2026-09-04T12:00:00+00:00")
```

- [ ] **Passo 9: implementar `atenuar_estado_offline` e tornar todos os testes GREEN**

A função deve calcular o decaimento com o tempo efetivo limitado e, depois, gravar o timestamp real de retomada e `EstadoConsciencia.RETOMANDO`.

- [ ] **Passo 10: regressão Atlas e commit**

```bash
python3 -m unittest discover -s infrastructure/pentium/atlas/tests -p 'test_*.py' -v
git add infrastructure/pentium/atlas/motor_afetivo.py infrastructure/pentium/atlas/tests/test_motor_afetivo.py
git commit -m "feat(atlas): implementar motor afetivo determinístico"
```

Esperado: todos GREEN.

---

### Tarefa 4: Persistência atômica e restauração segura

**Arquivos:**
- Criar: `infrastructure/pentium/atlas/persistencia_afetiva.py`
- Criar: `infrastructure/pentium/atlas/tests/test_persistencia_afetiva.py`

**Interfaces:**
- Consome: `EstadoAfetivo`, `PersonalidadeBase`, `PoliticaDecaimento`, `criar_estado_inicial`, `atenuar_estado_offline`.
- Produz:
  - `VERSAO_SNAPSHOT_AFETIVO = 1`;
  - `PersistenciaAfetivaError(RuntimeError)`;
  - `ResultadoRestauracao(estado: EstadoAfetivo, origem: str, erro: str | None)` frozen;
  - `salvar_estado_afetivo(path: Path, estado: EstadoAfetivo) -> None`;
  - `carregar_estado_afetivo(path: Path) -> EstadoAfetivo`;
  - `restaurar_estado_afetivo(path: Path, personalidade: PersonalidadeBase, politica: PoliticaDecaimento, retomado_em: str) -> ResultadoRestauracao`.

**Formato do snapshot:**

```json
{
  "versao": 1,
  "estado": {
    "valencia": 0.2,
    "ativacao": 0.25,
    "estresse": 0.1,
    "confianca": 0.7,
    "engajamento": 0.5,
    "curiosidade": 0.75,
    "foco_atencao": null,
    "estado_consciencia": "retomando",
    "atualizado_em": "2026-09-04T15:00:00+00:00"
  }
}
```

- [ ] **Passo 1: escrever teste RED de round-trip e escrita atômica**

```python
import json
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.modelo_afetivo import EstadoConsciencia, PersonalidadeBase, PoliticaDecaimento
from infrastructure.pentium.atlas.motor_afetivo import criar_estado_inicial
from infrastructure.pentium.atlas.persistencia_afetiva import carregar_estado_afetivo, salvar_estado_afetivo


class PersistenciaAfetivaTests(unittest.TestCase):
    def test_salva_e_carrega_snapshot_sem_deixar_temporario(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "estado-afetivo.json"
            personalidade = PersonalidadeBase(0.2, 0.25, 0.1, 0.7, 0.5, 0.75)
            estado = criar_estado_inicial(personalidade, "2026-09-04T15:00:00+00:00")
            salvar_estado_afetivo(path, estado)
            carregado = carregar_estado_afetivo(path)
            self.assertEqual(carregado, estado)
            self.assertFalse((Path(temp) / "estado-afetivo.json.tmp").exists())
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["versao"], 1)
```

- [ ] **Passo 2: executar e confirmar RED**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_persistencia_afetiva -v
```

Esperado: FAIL por módulo ausente.

- [ ] **Passo 3: implementar escrita atômica e loader estrito**

`salvar_estado_afetivo` deve:

```python
path.parent.mkdir(parents=True, exist_ok=True)
temporario = path.with_name(path.name + ".tmp")
with temporario.open("w", encoding="utf-8", newline="\n") as handle:
    json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
    handle.write("\n")
    handle.flush()
    os.fsync(handle.fileno())
os.replace(temporario, path)
```

Em qualquer `OSError`, remover o temporário quando possível e levantar `PersistenciaAfetivaError`. `carregar_estado_afetivo` rejeita versão diferente de 1, JSON inválido, campos ausentes, estado de consciência desconhecido e estrutura não objeto, convertendo falhas em `PersistenciaAfetivaError`.

- [ ] **Passo 4: executar o round-trip até GREEN**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_persistencia_afetiva -v
```

- [ ] **Passo 5: escrever testes RED de snapshot ausente/corrompido e restauração válida**

Adicionar casos:

```python
def test_snapshot_ausente_retorna_baseline_retomando(self):
    resultado = restaurar_estado_afetivo(
        Path("arquivo-que-nao-existe.json"),
        self.personalidade,
        self.politica,
        "2026-09-04T15:00:00+00:00",
    )
    self.assertEqual(resultado.origem, "baseline")
    self.assertEqual(resultado.erro, "snapshot_ausente")
    self.assertEqual(resultado.estado.estado_consciencia, EstadoConsciencia.RETOMANDO)


def test_snapshot_corrompido_nao_bloqueia_retomada(self):
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "estado.json"
        path.write_text("{invalido", encoding="utf-8")
        resultado = restaurar_estado_afetivo(
            path, self.personalidade, self.politica,
            "2026-09-04T15:00:00+00:00",
        )
        self.assertEqual(resultado.origem, "baseline")
        self.assertEqual(resultado.erro, "snapshot_invalido")


def test_snapshot_valido_aplica_atenuacao_offline_limitada(self):
    # salvar estado com estresse 0.9 às 00:00 e restaurar às 12:00
    # com meia-vida de estresse=1800 e limite offline=1800
    # esperado: estresse 0.5, origem snapshot, consciência retomando
```

- [ ] **Passo 6: confirmar RED e implementar `ResultadoRestauracao` + `restaurar_estado_afetivo`**

A restauração nunca engole silenciosamente falha: retorna `erro` explícito ao chamador. A1 não escolhe logger/journal; o consumidor futuro é responsável por registrar `erro`.

- [ ] **Passo 7: executar testes A1 + regressão Atlas**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_persistencia_afetiva -v
python3 -m unittest discover -s infrastructure/pentium/atlas/tests -p 'test_*.py' -v
```

Esperado: GREEN.

- [ ] **Passo 8: commit**

```bash
git add infrastructure/pentium/atlas/persistencia_afetiva.py infrastructure/pentium/atlas/tests/test_persistencia_afetiva.py
git commit -m "feat(atlas): persistir e restaurar estado afetivo"
```

---

### Tarefa 5: Empacotamento e gate de CI da A1

**Arquivos:**
- Criar: `infrastructure/pentium/atlas/tests/test_nucleo_afetivo_empacotamento.py`
- Modificar: `infrastructure/pentium/atlas/install-user.sh`
- Modificar: `.github/workflows/foundation-ci.yml`

**Interfaces:**
- Consome: todos os módulos A1.
- Produz markers:
  - installer: `ATLAS_NUCLEO_AFETIVO_INSTALL_PASS`;
  - CI: `DEVEX_HOMELAB_ATLAS_NUCLEO_AFETIVO_PASS`.

- [ ] **Passo 1: escrever teste RED do empacotamento**

```python
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ATLAS = ROOT / "infrastructure" / "pentium" / "atlas"
WORKFLOW = ROOT / ".github" / "workflows" / "foundation-ci.yml"


class NucleoAfetivoEmpacotamentoTests(unittest.TestCase):
    def test_installer_inclui_nucleo_afetivo_sem_ativar_servico(self):
        text = (ATLAS / "install-user.sh").read_text(encoding="utf-8")
        for nome in (
            "modelo_afetivo.py",
            "configuracao_afetiva.py",
            "motor_afetivo.py",
            "persistencia_afetiva.py",
            "config_afetiva.json",
        ):
            self.assertIn(nome, text)
        self.assertIn("ATLAS_NUCLEO_AFETIVO_INSTALL_PASS", text)
        lowered = text.lower()
        self.assertNotIn("systemctl enable", lowered)
        self.assertNotIn("systemctl start", lowered)

    def test_foundation_ci_compila_e_valida_a1(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("modelo_afetivo.py", text)
        self.assertIn("config_afetiva.json", text)
        self.assertIn("DEVEX_HOMELAB_ATLAS_NUCLEO_AFETIVO_PASS", text)
```

- [ ] **Passo 2: executar e confirmar RED**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_nucleo_afetivo_empacotamento -v
```

Esperado: FAIL porque installer/CI ainda não conhecem A1.

- [ ] **Passo 3: modificar `install-user.sh`**

Adicionar ao loop de módulos:

```text
modelo_afetivo.py
configuracao_afetiva.py
motor_afetivo.py
persistencia_afetiva.py
```

Adicionar `config_afetiva.json` ao loop de configs; incluir os quatro módulos no `py_compile`; validar JSON com `python3 -m json.tool`; emitir ao final:

```bash
echo "ATLAS_NUCLEO_AFETIVO_INSTALL_PASS"
```

Não alterar comportamento persistente do sistema.

- [ ] **Passo 4: modificar `.github/workflows/foundation-ci.yml`**

No gate Atlas existente, acrescentar os quatro módulos ao `py_compile`, validar `config_afetiva.json` e, depois dos testes, emitir:

```bash
echo 'DEVEX_HOMELAB_ATLAS_NUCLEO_AFETIVO_PASS'
```

- [ ] **Passo 5: executar gates locais de sintaxe/configuração**

```bash
python3 -m py_compile \
  infrastructure/pentium/atlas/modelo_afetivo.py \
  infrastructure/pentium/atlas/configuracao_afetiva.py \
  infrastructure/pentium/atlas/motor_afetivo.py \
  infrastructure/pentium/atlas/persistencia_afetiva.py
python3 -m json.tool infrastructure/pentium/atlas/config_afetiva.json >/dev/null
bash -n infrastructure/pentium/atlas/install-user.sh
python3 -m unittest infrastructure.pentium.atlas.tests.test_nucleo_afetivo_empacotamento -v
```

Esperado: PASS.

- [ ] **Passo 6: executar suíte completa do repositório usada no baseline**

```bash
python3 -m unittest discover -s infrastructure/network/tests -p 'test_*.py' -v
python3 -m unittest discover -s infrastructure/pentium/heartbeat/tests -p 'test_*.py' -v
python3 -m unittest discover -s infrastructure/pentium/agent/tests -p 'test_*.py' -v
python3 -m unittest discover -s infrastructure/pentium/atlas/tests -p 'test_*.py' -v
git diff --check
```

Esperado: Network 6, Heartbeat 7, Pentium Agent 10 e todos os Atlas legados + A1 GREEN; `git diff --check` sem saída.

- [ ] **Passo 7: commit**

```bash
git add .github/workflows/foundation-ci.yml infrastructure/pentium/atlas/install-user.sh infrastructure/pentium/atlas/tests/test_nucleo_afetivo_empacotamento.py
git commit -m "ci(atlas): certificar núcleo afetivo A1"
```

---

### Tarefa 6: Revisão de escopo, documentação final e PR Draft da A1

**Arquivos:**
- Modificar: `docs/as-built/2026-09-02-baseline.md`
- Não alterar: especificação aprovada, salvo correção factual comprovada.

**Interfaces:**
- Consome: resultados reais das Tarefas 1–5.
- Produz: evidência as-built e PR Draft stacked sobre `atlas/issue-20-observation-runtime`.

- [ ] **Passo 1: verificar que A1 não vazou responsabilidades de A2–A8**

Executar buscas:

```bash
git diff 1a28a54a051d152d83cf919a7f570e1bacccdf2e...HEAD -- infrastructure/pentium/atlas
grep -RniE 'grpc|https|socket|named pipe|traceroute|ssh|llm|tts|stt' infrastructure/pentium/atlas/modelo_afetivo.py infrastructure/pentium/atlas/configuracao_afetiva.py infrastructure/pentium/atlas/motor_afetivo.py infrastructure/pentium/atlas/persistencia_afetiva.py || true
```

Esperado: nenhuma implementação de transporte, diagnóstico ativo ou LLM em A1.

- [ ] **Passo 2: executar gate local final do HEAD exato**

```bash
HEAD_EXATO=$(git rev-parse HEAD)
echo "HEAD_EXATO=${HEAD_EXATO}"
python3 -m unittest discover -s infrastructure/network/tests -p 'test_*.py' -v
python3 -m unittest discover -s infrastructure/pentium/heartbeat/tests -p 'test_*.py' -v
python3 -m unittest discover -s infrastructure/pentium/agent/tests -p 'test_*.py' -v
python3 -m unittest discover -s infrastructure/pentium/atlas/tests -p 'test_*.py' -v
python3 -m json.tool infrastructure/pentium/atlas/config.json >/dev/null
python3 -m json.tool infrastructure/pentium/atlas/observation_config.json >/dev/null
python3 -m json.tool infrastructure/pentium/atlas/config_afetiva.json >/dev/null
bash -n infrastructure/pentium/atlas/install-user.sh
git diff --check
```

Registrar contagens reais; não antecipar número final de testes Atlas no documento.

- [ ] **Passo 3: atualizar as-built somente com fatos observados**

Adicionar seção `Atlas A1 — Núcleo Afetivo` contendo:

- SHA exato local certificado;
- contagens reais de Network/Heartbeat/Pentium Agent/Atlas;
- markers e validações executadas;
- módulos implementados;
- confirmação de zero LLM e zero mudança de rede/serviço persistente;
- declarar explicitamente se ainda não houve certificação física/soak.

Não registrar CI antes de ela existir.

- [ ] **Passo 4: commit da documentação**

```bash
git add docs/as-built/2026-09-02-baseline.md
git commit -m "docs(atlas): registrar implementação A1 do núcleo afetivo"
```

- [ ] **Passo 5: repetir gate após o commit documental**

Executar novamente a suíte completa e `git diff --check`, pois o HEAD mudou.

- [ ] **Passo 6: push e criação/atualização da PR Draft**

Push da branch `atlas/issue-20-motor-estado-afetivo`. Criar PR Draft com base `atlas/issue-20-observation-runtime` e título em pt-BR, por exemplo:

```text
feat(atlas): adicionar A1 núcleo afetivo determinístico
```

A PR deve permanecer Draft até gates e revisão explícita; não marcar Ready e não mergear automaticamente.

- [ ] **Passo 7: aguardar Foundation CI do HEAD exato e validar o mesmo SHA**

Somente aceitar GREEN se o workflow estiver `completed/success` no SHA exato da PR. Resultado de SHA anterior não vale.

- [ ] **Passo 8: checkpoint pt-BR da PR**

Publicar `/checkpoint` contendo:

- HEAD exato;
- o que A1 implementou;
- evidência RED→GREEN resumida;
- contagens locais reais;
- CI do mesmo SHA, se concluída;
- blockers/gates pendentes;
- nenhuma alegação de certificação física se não executada;
- próximo passo seguro: A2 — Entidades, vínculos e expectativas, somente após A1 permanecer GREEN.

---

## Auto-revisão do plano

### Cobertura da especificação para A1

A1 cobre deliberadamente apenas:

- `EstadoAfetivo` com seis dimensões e bounds;
- `PersonalidadeBase` persistente como linha de retorno;
- `ImpulsoAfetivo` limitado;
- `EstadoConsciencia` necessário à retomada;
- decaimento temporal diferente por dimensão;
- atenuação offline limitada;
- persistência atômica e fallback de snapshot inválido;
- gate/empacotamento sem serviço persistente.

Ficam explicitamente para slices posteriores, sem lacuna de A1: vínculo/entidades/expectativas (A2), percepção/correlação (A3), seleção de foco e emoções derivadas (A4), Agente de Nó C++ (A5), transportes (A6), diagnóstico ativo (A7) e integração/certificação ampla (A8).

### Consistência de tipos

- `EstadoAfetivo.atualizado_em` é sempre ISO-8601 aware em string.
- `foco_atencao` existe e persiste em A1, mas A1 não seleciona nem preempta foco.
- `EstadoConsciencia` existe em A1 para bootstrap/restauração; transições operacionais completas virão com integração posterior.
- Decaimento e restauração recebem tempo explicitamente; não consultam relógio global oculto.
- Snapshot v1 contém apenas estado necessário à A1; incidentes/expectativas serão adicionados por migração de schema quando A2/A3 existirem, não por campos vazios antecipados.

### Ausência de placeholders

O plano não contém `TBD`/`TODO`; valores iniciais, assinaturas, fórmula de decaimento, schema, comandos de teste e markers estão definidos. Metas de CPU/RAM continuam fora de A1 porque a especificação exige medi-las antes de fixar números de certificação.