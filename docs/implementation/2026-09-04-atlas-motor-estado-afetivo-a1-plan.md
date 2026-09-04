# A1 — Núcleo Afetivo — Plano de Implementação

> **Para execução agentic:** SUB-SKILL OBRIGATÓRIA: usar `superpowers:subagent-driven-development` (recomendado) ou `superpowers:executing-plans` para executar este plano tarefa por tarefa. Os passos usam caixas `- [ ]` para acompanhamento.

**Objetivo:** implementar o núcleo afetivo determinístico do Atlas com estado de seis dimensões, personalidade-base, impulsos limitados, decaimento temporal por meia-vida, persistência atômica e retomada com atenuação offline limitada.

**Arquitetura:** a A1 é uma camada pura e independente do `ObservationRuntime`: recebe `ImpulsoAfetivo` já contextualizado, aplica decaimento e atualização bounded sobre `EstadoAfetivo`, e persiste snapshots locais. Não implementa vínculos, correlação, foco dinâmico, agentes C++, transporte, diagnóstico ativo, LLM, áudio ou ações de controle.

**Stack técnica:** Python 3.14 compatível com a base atual, `dataclasses`, `datetime`, `json`, `math`, `os`, `pathlib`, `unittest`; sem dependência Python externa.

**Especificação:** `docs/implementation/2026-09-04-atlas-motor-estado-afetivo-design.md`

## Restrições globais

- Todo novo contrato, documentação, teste, mensagem e checkpoint desta sub-slice deve estar em português do Brasil; identificadores Python novos usam português sem acentos.
- Contratos legados certificados (`Stimulus`, `ObservationRuntime`, `ReactionEngine` etc.) não serão renomeados nesta sub-slice.
- O estado técnico continua autoritativo; A1 não lê nem reclassifica saúde técnica.
- A LLM não participa da A1 e o número de chamadas de LLM deve permanecer zero.
- Nenhuma alteração de rede, SSH, Tailscale, firewall, modem, rota, DNS, systemd ou serviço persistente é permitida.
- Todas as dimensões são bounded: `valencia` em `-1.0..+1.0`; demais dimensões em `0.0..1.0`.
- Decaimento usa tempo absoluto UTC e fórmula exponencial por meia-vida, independente da quantidade de ciclos.
- Durante período offline, o decaimento efetivo é limitado a no máximo `3600` segundos, mesmo que o Pentium permaneça desligado por mais tempo.
- A configuração inicial da personalidade é explícita e versionada em JSON; nenhum valor é inferido pela LLM.
- TDD é obrigatório: cada tarefa de código começa com teste RED, segue com implementação mínima GREEN e termina com commit próprio.
- A branch permanece empilhada sobre `atlas/issue-20-observation-runtime`; não marcar Ready nem realizar merge durante A1 sem decisão explícita.

## Estrutura de arquivos da A1

- `infrastructure/pentium/atlas/modelo_afetivo.py`: contratos puros `EstadoAfetivo`, `PersonalidadeBase`, `ImpulsoAfetivo` e `PoliticaDecaimento`.
- `infrastructure/pentium/atlas/configuracao_afetiva.py`: carregamento e validação do JSON de personalidade/decaimento.
- `infrastructure/pentium/atlas/config_afetiva.json`: valores iniciais versionados da personalidade e das meias-vidas.
- `infrastructure/pentium/atlas/decaimento_afetivo.py`: função pura de aproximação exponencial ao baseline, incluindo modo offline limitado.
- `infrastructure/pentium/atlas/motor_afetivo.py`: estado em memória e aplicação determinística de impulsos.
- `infrastructure/pentium/atlas/persistencia_afetiva.py`: snapshot JSON atômico, restauração e fallback explícito.
- `infrastructure/pentium/atlas/tests/test_modelo_afetivo.py`: invariantes e limites do modelo.
- `infrastructure/pentium/atlas/tests/test_configuracao_afetiva.py`: contrato do JSON e valores canônicos iniciais.
- `infrastructure/pentium/atlas/tests/test_decaimento_afetivo.py`: meia-vida, relógio e limite offline.
- `infrastructure/pentium/atlas/tests/test_motor_afetivo.py`: aplicação de impulsos e ordenação temporal.
- `infrastructure/pentium/atlas/tests/test_persistencia_afetiva.py`: round-trip, corrupção, ausência e retomada offline.
- `infrastructure/pentium/atlas/tests/test_a1_empacotamento.py`: instalador e gate de CI.
- `infrastructure/pentium/atlas/install-user.sh`: incluir os novos módulos/configuração sem ativar serviço.
- `.github/workflows/foundation-ci.yml`: compilar os novos módulos, validar o JSON e publicar marcador A1.
- `docs/as-built/2026-09-02-baseline.md`: registrar somente evidência efetivamente obtida após GREEN no SHA exato.

---

### Tarefa 1: Contratos puros do núcleo afetivo

**Arquivos:**
- Criar: `infrastructure/pentium/atlas/modelo_afetivo.py`
- Criar: `infrastructure/pentium/atlas/tests/test_modelo_afetivo.py`

**Interfaces:**
- Consome: apenas biblioteca padrão.
- Produz:
  - `EstadoAfetivo(valencia, ativacao, estresse, confianca, engajamento, curiosidade, atualizado_em, foco_atencao=None)`;
  - `PersonalidadeBase(...).criar_estado(atualizado_em: str) -> EstadoAfetivo`;
  - `ImpulsoAfetivo(motivo, delta_valencia=0.0, delta_ativacao=0.0, delta_estresse=0.0, delta_confianca=0.0, delta_engajamento=0.0, delta_curiosidade=0.0)`;
  - `PoliticaDecaimento(meia_vida_valencia_s, meia_vida_ativacao_s, meia_vida_estresse_s, meia_vida_confianca_s, meia_vida_engajamento_s, meia_vida_curiosidade_s, atenuacao_offline_maxima_s)`.

- [ ] **Passo 1: escrever o teste RED do modelo**

Criar `test_modelo_afetivo.py` com:

```python
import unittest

from infrastructure.pentium.atlas.modelo_afetivo import (
    EstadoAfetivo,
    ImpulsoAfetivo,
    PersonalidadeBase,
)


class ModeloAfetivoTests(unittest.TestCase):
    def test_estado_limita_dimensoes_ao_intervalo_canonico(self):
        estado = EstadoAfetivo(
            valencia=2.0,
            ativacao=1.5,
            estresse=-0.4,
            confianca=1.2,
            engajamento=-1.0,
            curiosidade=0.6,
            atualizado_em="2026-09-04T12:00:00+00:00",
        )
        self.assertEqual(1.0, estado.valencia)
        self.assertEqual(1.0, estado.ativacao)
        self.assertEqual(0.0, estado.estresse)
        self.assertEqual(1.0, estado.confianca)
        self.assertEqual(0.0, estado.engajamento)
        self.assertEqual(0.6, estado.curiosidade)

    def test_impulso_rejeita_delta_fora_de_menos_um_a_mais_um(self):
        with self.assertRaises(ValueError):
            ImpulsoAfetivo(motivo="teste", delta_estresse=1.01)

    def test_personalidade_cria_estado_exatamente_no_baseline(self):
        personalidade = PersonalidadeBase(
            valencia=0.20,
            ativacao=0.25,
            estresse=0.10,
            confianca=0.70,
            engajamento=0.55,
            curiosidade=0.75,
        )
        estado = personalidade.criar_estado("2026-09-04T12:00:00+00:00")
        self.assertEqual(0.20, estado.valencia)
        self.assertEqual(0.10, estado.estresse)
        self.assertEqual(0.75, estado.curiosidade)
        self.assertIsNone(estado.foco_atencao)
```

- [ ] **Passo 2: executar o teste e confirmar RED**

Executar:

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_modelo_afetivo -v
```

Resultado esperado: falha de importação porque `modelo_afetivo.py` ainda não existe.

- [ ] **Passo 3: implementar o modelo mínimo**

Criar `modelo_afetivo.py` com a seguinte estrutura e invariantes:

```python
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime


def _finito(valor: float, nome: str) -> float:
    numero = float(valor)
    if not math.isfinite(numero):
        raise ValueError(f"{nome} deve ser finito")
    return numero


def _limitar(valor: float, minimo: float, maximo: float, nome: str) -> float:
    numero = _finito(valor, nome)
    return max(minimo, min(maximo, numero))


def _validar_intervalo(valor: float, minimo: float, maximo: float, nome: str) -> float:
    numero = _finito(valor, nome)
    if not minimo <= numero <= maximo:
        raise ValueError(f"{nome} deve estar entre {minimo} e {maximo}")
    return numero


def _validar_instante(valor: str) -> str:
    instante = datetime.fromisoformat(valor)
    if instante.tzinfo is None or instante.utcoffset() is None:
        raise ValueError("atualizado_em deve possuir timezone")
    return valor


@dataclass(frozen=True)
class EstadoAfetivo:
    valencia: float
    ativacao: float
    estresse: float
    confianca: float
    engajamento: float
    curiosidade: float
    atualizado_em: str
    foco_atencao: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "valencia", _limitar(self.valencia, -1.0, 1.0, "valencia"))
        for nome in ("ativacao", "estresse", "confianca", "engajamento", "curiosidade"):
            object.__setattr__(self, nome, _limitar(getattr(self, nome), 0.0, 1.0, nome))
        object.__setattr__(self, "atualizado_em", _validar_instante(self.atualizado_em))


@dataclass(frozen=True)
class PersonalidadeBase:
    valencia: float
    ativacao: float
    estresse: float
    confianca: float
    engajamento: float
    curiosidade: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "valencia", _validar_intervalo(self.valencia, -1.0, 1.0, "valencia"))
        for nome in ("ativacao", "estresse", "confianca", "engajamento", "curiosidade"):
            object.__setattr__(self, nome, _validar_intervalo(getattr(self, nome), 0.0, 1.0, nome))

    def criar_estado(self, atualizado_em: str) -> EstadoAfetivo:
        return EstadoAfetivo(
            self.valencia,
            self.ativacao,
            self.estresse,
            self.confianca,
            self.engajamento,
            self.curiosidade,
            atualizado_em,
        )


@dataclass(frozen=True)
class ImpulsoAfetivo:
    motivo: str
    delta_valencia: float = 0.0
    delta_ativacao: float = 0.0
    delta_estresse: float = 0.0
    delta_confianca: float = 0.0
    delta_engajamento: float = 0.0
    delta_curiosidade: float = 0.0

    def __post_init__(self) -> None:
        if not self.motivo.strip():
            raise ValueError("motivo não pode ser vazio")
        for nome in (
            "delta_valencia", "delta_ativacao", "delta_estresse",
            "delta_confianca", "delta_engajamento", "delta_curiosidade",
        ):
            object.__setattr__(self, nome, _validar_intervalo(getattr(self, nome), -1.0, 1.0, nome))


@dataclass(frozen=True)
class PoliticaDecaimento:
    meia_vida_valencia_s: float
    meia_vida_ativacao_s: float
    meia_vida_estresse_s: float
    meia_vida_confianca_s: float
    meia_vida_engajamento_s: float
    meia_vida_curiosidade_s: float
    atenuacao_offline_maxima_s: float

    def __post_init__(self) -> None:
        for nome in (
            "meia_vida_valencia_s", "meia_vida_ativacao_s", "meia_vida_estresse_s",
            "meia_vida_confianca_s", "meia_vida_engajamento_s", "meia_vida_curiosidade_s",
        ):
            if _finito(getattr(self, nome), nome) <= 0:
                raise ValueError(f"{nome} deve ser > 0")
        if _finito(self.atenuacao_offline_maxima_s, "atenuacao_offline_maxima_s") < 0:
            raise ValueError("atenuacao_offline_maxima_s deve ser >= 0")
```

- [ ] **Passo 4: executar o teste e confirmar GREEN**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_modelo_afetivo -v
```

Resultado esperado: `Ran 3 tests ... OK`.

- [ ] **Passo 5: executar regressão Atlas e commit**

```bash
python3 -m unittest discover -s infrastructure/pentium/atlas/tests -p 'test_*.py' -v
git add infrastructure/pentium/atlas/modelo_afetivo.py infrastructure/pentium/atlas/tests/test_modelo_afetivo.py
git commit -m "feat(atlas): adicionar contratos do nucleo afetivo"
```

---

### Tarefa 2: Configuração versionada da personalidade e do decaimento

**Arquivos:**
- Criar: `infrastructure/pentium/atlas/configuracao_afetiva.py`
- Criar: `infrastructure/pentium/atlas/config_afetiva.json`
- Criar: `infrastructure/pentium/atlas/tests/test_configuracao_afetiva.py`

**Interfaces:**
- Consome: `PersonalidadeBase`, `PoliticaDecaimento`.
- Produz: `ConfiguracaoAfetiva` e `carregar_configuracao_afetiva(path: Path) -> ConfiguracaoAfetiva`.

- [ ] **Passo 1: escrever o teste RED da configuração**

Criar `test_configuracao_afetiva.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.configuracao_afetiva import carregar_configuracao_afetiva


ROOT = Path(__file__).resolve().parents[4]
CONFIG = ROOT / "infrastructure" / "pentium" / "atlas" / "config_afetiva.json"


class ConfiguracaoAfetivaTests(unittest.TestCase):
    def test_configuracao_do_repositorio_carrega_baseline_e_meias_vidas(self):
        cfg = carregar_configuracao_afetiva(CONFIG)
        self.assertEqual(0.20, cfg.personalidade.valencia)
        self.assertEqual(0.10, cfg.personalidade.estresse)
        self.assertEqual(0.75, cfg.personalidade.curiosidade)
        self.assertEqual(900.0, cfg.decaimento.meia_vida_ativacao_s)
        self.assertEqual(3600.0, cfg.decaimento.atenuacao_offline_maxima_s)

    def test_schema_version_diferente_de_um_e_rejeitado(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({"schema_version": 2}), encoding="utf-8")
            with self.assertRaises(ValueError):
                carregar_configuracao_afetiva(path)

    def test_meia_vida_nao_positiva_e_rejeitada(self):
        payload = json.loads(CONFIG.read_text(encoding="utf-8"))
        payload["decaimento"]["meia_vida_ativacao_s"] = 0
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                carregar_configuracao_afetiva(path)
```

- [ ] **Passo 2: executar e confirmar RED**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_configuracao_afetiva -v
```

Resultado esperado: falha de importação porque `configuracao_afetiva.py` ainda não existe.

- [ ] **Passo 3: criar o JSON canônico da A1**

Criar `config_afetiva.json` exatamente com:

```json
{
  "schema_version": 1,
  "personalidade_base": {
    "valencia": 0.20,
    "ativacao": 0.25,
    "estresse": 0.10,
    "confianca": 0.70,
    "engajamento": 0.55,
    "curiosidade": 0.75
  },
  "decaimento": {
    "meia_vida_valencia_s": 3600,
    "meia_vida_ativacao_s": 900,
    "meia_vida_estresse_s": 1800,
    "meia_vida_confianca_s": 21600,
    "meia_vida_engajamento_s": 7200,
    "meia_vida_curiosidade_s": 10800,
    "atenuacao_offline_maxima_s": 3600
  }
}
```

Esses valores são configuração inicial explícita, não regra hardcoded do motor.

- [ ] **Passo 4: implementar o loader mínimo**

Criar `configuracao_afetiva.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .modelo_afetivo import PersonalidadeBase, PoliticaDecaimento


@dataclass(frozen=True)
class ConfiguracaoAfetiva:
    personalidade: PersonalidadeBase
    decaimento: PoliticaDecaimento


def carregar_configuracao_afetiva(path: Path) -> ConfiguracaoAfetiva:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("config afetiva schema_version deve ser 1")
    try:
        personalidade = PersonalidadeBase(**payload["personalidade_base"])
        decaimento = PoliticaDecaimento(**payload["decaimento"])
    except KeyError as exc:
        raise ValueError(f"config afetiva sem campo obrigatório: {exc.args[0]}") from exc
    return ConfiguracaoAfetiva(personalidade, decaimento)
```

- [ ] **Passo 5: validar JSON, testes e commit**

```bash
python3 -m json.tool infrastructure/pentium/atlas/config_afetiva.json >/dev/null
python3 -m unittest infrastructure.pentium.atlas.tests.test_configuracao_afetiva -v
python3 -m unittest discover -s infrastructure/pentium/atlas/tests -p 'test_*.py' -v
git add infrastructure/pentium/atlas/configuracao_afetiva.py infrastructure/pentium/atlas/config_afetiva.json infrastructure/pentium/atlas/tests/test_configuracao_afetiva.py
git commit -m "feat(atlas): configurar personalidade e decaimento afetivo"
```

Resultado esperado do teste específico: `Ran 3 tests ... OK`.

---

### Tarefa 3: Decaimento exponencial determinístico e limite offline

**Arquivos:**
- Criar: `infrastructure/pentium/atlas/decaimento_afetivo.py`
- Criar: `infrastructure/pentium/atlas/tests/test_decaimento_afetivo.py`

**Interfaces:**
- Consome: `EstadoAfetivo`, `PersonalidadeBase`, `PoliticaDecaimento`.
- Produz: `decair_estado(estado, personalidade, politica, agora, modo_offline=False) -> EstadoAfetivo`.

A fórmula canônica por dimensão é:

```text
novo = baseline + (atual - baseline) * 0.5 ** (segundos_efetivos / meia_vida)
```

No modo offline:

```text
segundos_efetivos = min(segundos_decorridos, atenuacao_offline_maxima_s)
```

- [ ] **Passo 1: escrever o teste RED do decaimento**

Criar `test_decaimento_afetivo.py`:

```python
import unittest

from infrastructure.pentium.atlas.decaimento_afetivo import decair_estado
from infrastructure.pentium.atlas.modelo_afetivo import EstadoAfetivo, PersonalidadeBase, PoliticaDecaimento


PERSONALIDADE = PersonalidadeBase(0.20, 0.25, 0.10, 0.70, 0.55, 0.75)
POLITICA = PoliticaDecaimento(3600, 900, 1800, 21600, 7200, 10800, 3600)


class DecaimentoAfetivoTests(unittest.TestCase):
    def test_uma_meia_vida_reduz_metade_da_distancia_ao_baseline(self):
        estado = EstadoAfetivo(0.80, 0.25, 0.10, 0.70, 0.55, 0.75, "2026-09-04T12:00:00+00:00")
        novo = decair_estado(estado, PERSONALIDADE, POLITICA, "2026-09-04T13:00:00+00:00")
        self.assertAlmostEqual(0.50, novo.valencia, places=9)

    def test_modo_offline_limita_decaimento_a_uma_hora(self):
        estado = EstadoAfetivo(0.80, 0.25, 0.10, 0.70, 0.55, 0.75, "2026-09-04T00:00:00+00:00")
        novo = decair_estado(estado, PERSONALIDADE, POLITICA, "2026-09-04T12:00:00+00:00", modo_offline=True)
        self.assertAlmostEqual(0.50, novo.valencia, places=9)
        self.assertEqual("2026-09-04T12:00:00+00:00", novo.atualizado_em)

    def test_instante_anterior_ao_estado_e_rejeitado(self):
        estado = PERSONALIDADE.criar_estado("2026-09-04T12:00:00+00:00")
        with self.assertRaises(ValueError):
            decair_estado(estado, PERSONALIDADE, POLITICA, "2026-09-04T11:59:59+00:00")
```

- [ ] **Passo 2: executar e confirmar RED**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_decaimento_afetivo -v
```

Resultado esperado: falha de importação porque `decaimento_afetivo.py` ainda não existe.

- [ ] **Passo 3: implementar o decaimento mínimo**

Criar `decaimento_afetivo.py`:

```python
from __future__ import annotations

from datetime import datetime

from .modelo_afetivo import EstadoAfetivo, PersonalidadeBase, PoliticaDecaimento


def _segundos(inicio: str, fim: str) -> float:
    a = datetime.fromisoformat(inicio)
    b = datetime.fromisoformat(fim)
    if a.tzinfo is None or b.tzinfo is None:
        raise ValueError("instantes devem possuir timezone")
    segundos = (b - a).total_seconds()
    if segundos < 0:
        raise ValueError("agora não pode ser anterior ao estado")
    return segundos


def _aproximar(atual: float, baseline: float, meia_vida_s: float, segundos: float) -> float:
    return baseline + (atual - baseline) * (0.5 ** (segundos / meia_vida_s))


def decair_estado(
    estado: EstadoAfetivo,
    personalidade: PersonalidadeBase,
    politica: PoliticaDecaimento,
    agora: str,
    *,
    modo_offline: bool = False,
) -> EstadoAfetivo:
    decorridos = _segundos(estado.atualizado_em, agora)
    efetivos = min(decorridos, politica.atenuacao_offline_maxima_s) if modo_offline else decorridos
    return EstadoAfetivo(
        valencia=_aproximar(estado.valencia, personalidade.valencia, politica.meia_vida_valencia_s, efetivos),
        ativacao=_aproximar(estado.ativacao, personalidade.ativacao, politica.meia_vida_ativacao_s, efetivos),
        estresse=_aproximar(estado.estresse, personalidade.estresse, politica.meia_vida_estresse_s, efetivos),
        confianca=_aproximar(estado.confianca, personalidade.confianca, politica.meia_vida_confianca_s, efetivos),
        engajamento=_aproximar(estado.engajamento, personalidade.engajamento, politica.meia_vida_engajamento_s, efetivos),
        curiosidade=_aproximar(estado.curiosidade, personalidade.curiosidade, politica.meia_vida_curiosidade_s, efetivos),
        atualizado_em=agora,
        foco_atencao=estado.foco_atencao,
    )
```

- [ ] **Passo 4: executar e confirmar GREEN**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_decaimento_afetivo -v
```

Resultado esperado: `Ran 3 tests ... OK`.

- [ ] **Passo 5: regressão e commit**

```bash
python3 -m unittest discover -s infrastructure/pentium/atlas/tests -p 'test_*.py' -v
git add infrastructure/pentium/atlas/decaimento_afetivo.py infrastructure/pentium/atlas/tests/test_decaimento_afetivo.py
git commit -m "feat(atlas): adicionar decaimento temporal afetivo"
```

---

### Tarefa 4: Motor em memória e aplicação de impulsos

**Arquivos:**
- Criar: `infrastructure/pentium/atlas/motor_afetivo.py`
- Criar: `infrastructure/pentium/atlas/tests/test_motor_afetivo.py`

**Interfaces:**
- Consome: modelo e `decair_estado`.
- Produz:
  - `MotorEstadoAfetivo(personalidade, politica, estado_inicial, relogio)`;
  - propriedade `estado_atual -> EstadoAfetivo`;
  - `decair_ate(agora=None, modo_offline=False) -> EstadoAfetivo`;
  - `aplicar_impulso(impulso, ocorrido_em=None) -> EstadoAfetivo`.

A1 não escolhe `foco_atencao`; apenas preserva o valor existente. A lógica de foco pertence à A4.

- [ ] **Passo 1: escrever o teste RED do motor**

Criar `test_motor_afetivo.py`:

```python
import unittest

from infrastructure.pentium.atlas.modelo_afetivo import EstadoAfetivo, ImpulsoAfetivo, PersonalidadeBase, PoliticaDecaimento
from infrastructure.pentium.atlas.motor_afetivo import MotorEstadoAfetivo


PERSONALIDADE = PersonalidadeBase(0.20, 0.25, 0.10, 0.70, 0.55, 0.75)
POLITICA = PoliticaDecaimento(3600, 900, 1800, 21600, 7200, 10800, 3600)


class MotorEstadoAfetivoTests(unittest.TestCase):
    def test_impulso_aplica_decaimento_antes_do_delta(self):
        inicial = EstadoAfetivo(0.80, 0.25, 0.10, 0.70, 0.55, 0.75, "2026-09-04T12:00:00+00:00")
        motor = MotorEstadoAfetivo(PERSONALIDADE, POLITICA, inicial, lambda: "2026-09-04T13:00:00+00:00")
        novo = motor.aplicar_impulso(ImpulsoAfetivo("recuperacao", delta_valencia=0.10))
        self.assertAlmostEqual(0.60, novo.valencia, places=9)

    def test_impulso_nao_pode_ultrapassar_limites_do_estado(self):
        inicial = PERSONALIDADE.criar_estado("2026-09-04T12:00:00+00:00")
        motor = MotorEstadoAfetivo(PERSONALIDADE, POLITICA, inicial, lambda: "2026-09-04T12:00:00+00:00")
        novo = motor.aplicar_impulso(ImpulsoAfetivo("critico", delta_estresse=1.0, delta_ativacao=1.0))
        self.assertEqual(1.0, novo.estresse)
        self.assertEqual(1.0, novo.ativacao)

    def test_a1_preserva_foco_sem_tentar_decidi_lo(self):
        inicial = EstadoAfetivo(0.20, 0.25, 0.10, 0.70, 0.55, 0.75, "2026-09-04T12:00:00+00:00", "x99")
        motor = MotorEstadoAfetivo(PERSONALIDADE, POLITICA, inicial, lambda: "2026-09-04T12:00:00+00:00")
        novo = motor.aplicar_impulso(ImpulsoAfetivo("teste", delta_curiosidade=0.10))
        self.assertEqual("x99", novo.foco_atencao)
```

- [ ] **Passo 2: executar e confirmar RED**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_motor_afetivo -v
```

Resultado esperado: falha de importação porque `motor_afetivo.py` ainda não existe.

- [ ] **Passo 3: implementar o motor mínimo**

Criar `motor_afetivo.py`:

```python
from __future__ import annotations

from collections.abc import Callable

from .decaimento_afetivo import decair_estado
from .modelo_afetivo import EstadoAfetivo, ImpulsoAfetivo, PersonalidadeBase, PoliticaDecaimento


class MotorEstadoAfetivo:
    def __init__(
        self,
        personalidade: PersonalidadeBase,
        politica: PoliticaDecaimento,
        estado_inicial: EstadoAfetivo,
        relogio: Callable[[], str],
    ):
        self._personalidade = personalidade
        self._politica = politica
        self._estado = estado_inicial
        self._relogio = relogio

    @property
    def estado_atual(self) -> EstadoAfetivo:
        return self._estado

    def decair_ate(self, agora: str | None = None, *, modo_offline: bool = False) -> EstadoAfetivo:
        instante = agora or self._relogio()
        self._estado = decair_estado(
            self._estado,
            self._personalidade,
            self._politica,
            instante,
            modo_offline=modo_offline,
        )
        return self._estado

    def aplicar_impulso(self, impulso: ImpulsoAfetivo, ocorrido_em: str | None = None) -> EstadoAfetivo:
        instante = ocorrido_em or self._relogio()
        base = self.decair_ate(instante)
        self._estado = EstadoAfetivo(
            valencia=base.valencia + impulso.delta_valencia,
            ativacao=base.ativacao + impulso.delta_ativacao,
            estresse=base.estresse + impulso.delta_estresse,
            confianca=base.confianca + impulso.delta_confianca,
            engajamento=base.engajamento + impulso.delta_engajamento,
            curiosidade=base.curiosidade + impulso.delta_curiosidade,
            atualizado_em=instante,
            foco_atencao=base.foco_atencao,
        )
        return self._estado
```

- [ ] **Passo 4: executar e confirmar GREEN**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_motor_afetivo -v
```

Resultado esperado: `Ran 3 tests ... OK`.

- [ ] **Passo 5: regressão e commit**

```bash
python3 -m unittest discover -s infrastructure/pentium/atlas/tests -p 'test_*.py' -v
git add infrastructure/pentium/atlas/motor_afetivo.py infrastructure/pentium/atlas/tests/test_motor_afetivo.py
git commit -m "feat(atlas): implementar motor de estado afetivo A1"
```

---

### Tarefa 5: Persistência atômica e restauração segura

**Arquivos:**
- Criar: `infrastructure/pentium/atlas/persistencia_afetiva.py`
- Criar: `infrastructure/pentium/atlas/tests/test_persistencia_afetiva.py`

**Interfaces:**
- Consome: `EstadoAfetivo`, `PersonalidadeBase`, `PoliticaDecaimento`, `decair_estado`.
- Produz:
  - `SnapshotAfetivoInvalido`;
  - enum `OrigemRestauracaoAfetiva` com `SNAPSHOT`, `BASELINE_AUSENTE`, `BASELINE_CORROMPIDO`;
  - `ResultadoRestauracaoAfetiva(estado, origem, erro)`;
  - `RepositorioEstadoAfetivo(path).salvar(estado)`;
  - `RepositorioEstadoAfetivo(path).carregar() -> EstadoAfetivo | None`;
  - `restaurar_estado(repositorio, personalidade, politica, agora) -> ResultadoRestauracaoAfetiva`.

- [ ] **Passo 1: escrever o teste RED da persistência**

Criar `test_persistencia_afetiva.py`:

```python
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.modelo_afetivo import EstadoAfetivo, PersonalidadeBase, PoliticaDecaimento
from infrastructure.pentium.atlas.persistencia_afetiva import (
    OrigemRestauracaoAfetiva,
    RepositorioEstadoAfetivo,
    restaurar_estado,
)


PERSONALIDADE = PersonalidadeBase(0.20, 0.25, 0.10, 0.70, 0.55, 0.75)
POLITICA = PoliticaDecaimento(3600, 900, 1800, 21600, 7200, 10800, 3600)


class PersistenciaAfetivaTests(unittest.TestCase):
    def test_salvar_e_carregar_preserva_estado(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = RepositorioEstadoAfetivo(Path(tmp) / "estado.json")
            estado = EstadoAfetivo(0.40, 0.60, 0.80, 0.50, 0.70, 0.90, "2026-09-04T12:00:00+00:00", "core")
            repo.salvar(estado)
            self.assertEqual(estado, repo.carregar())
            self.assertFalse((Path(tmp) / "estado.json.tmp").exists())

    def test_snapshot_corrompido_retorna_baseline_com_erro_explicito(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "estado.json"
            path.write_text("{quebrado", encoding="utf-8")
            resultado = restaurar_estado(RepositorioEstadoAfetivo(path), PERSONALIDADE, POLITICA, "2026-09-04T12:00:00+00:00")
            self.assertEqual(OrigemRestauracaoAfetiva.BASELINE_CORROMPIDO, resultado.origem)
            self.assertIsNotNone(resultado.erro)
            self.assertEqual(0.10, resultado.estado.estresse)

    def test_snapshot_ausente_retorna_baseline_sem_erro(self):
        with tempfile.TemporaryDirectory() as tmp:
            resultado = restaurar_estado(RepositorioEstadoAfetivo(Path(tmp) / "estado.json"), PERSONALIDADE, POLITICA, "2026-09-04T12:00:00+00:00")
            self.assertEqual(OrigemRestauracaoAfetiva.BASELINE_AUSENTE, resultado.origem)
            self.assertIsNone(resultado.erro)
            self.assertEqual(0.20, resultado.estado.valencia)

    def test_restauracao_aplica_apenas_uma_hora_de_atenuacao_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = RepositorioEstadoAfetivo(Path(tmp) / "estado.json")
            repo.salvar(EstadoAfetivo(0.80, 0.25, 0.10, 0.70, 0.55, 0.75, "2026-09-04T00:00:00+00:00"))
            resultado = restaurar_estado(repo, PERSONALIDADE, POLITICA, "2026-09-04T12:00:00+00:00")
            self.assertEqual(OrigemRestauracaoAfetiva.SNAPSHOT, resultado.origem)
            self.assertAlmostEqual(0.50, resultado.estado.valencia, places=9)
```

- [ ] **Passo 2: executar e confirmar RED**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_persistencia_afetiva -v
```

Resultado esperado: falha de importação porque `persistencia_afetiva.py` ainda não existe.

- [ ] **Passo 3: implementar persistência e fallback**

Criar `persistencia_afetiva.py`:

```python
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .decaimento_afetivo import decair_estado
from .modelo_afetivo import EstadoAfetivo, PersonalidadeBase, PoliticaDecaimento


class SnapshotAfetivoInvalido(ValueError):
    pass


class OrigemRestauracaoAfetiva(str, Enum):
    SNAPSHOT = "snapshot"
    BASELINE_AUSENTE = "baseline_ausente"
    BASELINE_CORROMPIDO = "baseline_corrompido"


@dataclass(frozen=True)
class ResultadoRestauracaoAfetiva:
    estado: EstadoAfetivo
    origem: OrigemRestauracaoAfetiva
    erro: str | None = None


class RepositorioEstadoAfetivo:
    def __init__(self, caminho: Path):
        self._caminho = Path(caminho)

    def salvar(self, estado: EstadoAfetivo) -> None:
        self._caminho.parent.mkdir(parents=True, exist_ok=True)
        temporario = self._caminho.with_name(self._caminho.name + ".tmp")
        payload = {
            "schema_version": 1,
            "estado": {
                "valencia": estado.valencia,
                "ativacao": estado.ativacao,
                "estresse": estado.estresse,
                "confianca": estado.confianca,
                "engajamento": estado.engajamento,
                "curiosidade": estado.curiosidade,
                "atualizado_em": estado.atualizado_em,
                "foco_atencao": estado.foco_atencao,
            },
        }
        try:
            with temporario.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporario, self._caminho)
        finally:
            temporario.unlink(missing_ok=True)

    def carregar(self) -> EstadoAfetivo | None:
        if not self._caminho.exists():
            return None
        try:
            payload = json.loads(self._caminho.read_text(encoding="utf-8"))
            if payload.get("schema_version") != 1:
                raise ValueError("snapshot schema_version deve ser 1")
            return EstadoAfetivo(**payload["estado"])
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise SnapshotAfetivoInvalido(str(exc)) from exc


def restaurar_estado(
    repositorio: RepositorioEstadoAfetivo,
    personalidade: PersonalidadeBase,
    politica: PoliticaDecaimento,
    agora: str,
) -> ResultadoRestauracaoAfetiva:
    try:
        estado = repositorio.carregar()
    except SnapshotAfetivoInvalido as exc:
        return ResultadoRestauracaoAfetiva(
            personalidade.criar_estado(agora),
            OrigemRestauracaoAfetiva.BASELINE_CORROMPIDO,
            str(exc),
        )
    if estado is None:
        return ResultadoRestauracaoAfetiva(
            personalidade.criar_estado(agora),
            OrigemRestauracaoAfetiva.BASELINE_AUSENTE,
        )
    return ResultadoRestauracaoAfetiva(
        decair_estado(estado, personalidade, politica, agora, modo_offline=True),
        OrigemRestauracaoAfetiva.SNAPSHOT,
    )
```

- [ ] **Passo 4: executar e confirmar GREEN**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_persistencia_afetiva -v
```

Resultado esperado: `Ran 4 tests ... OK`.

- [ ] **Passo 5: regressão e commit**

```bash
python3 -m unittest discover -s infrastructure/pentium/atlas/tests -p 'test_*.py' -v
git add infrastructure/pentium/atlas/persistencia_afetiva.py infrastructure/pentium/atlas/tests/test_persistencia_afetiva.py
git commit -m "feat(atlas): persistir estado afetivo com retomada segura"
```

---

### Tarefa 6: Empacotamento user-level e Foundation CI

**Arquivos:**
- Criar: `infrastructure/pentium/atlas/tests/test_a1_empacotamento.py`
- Modificar: `infrastructure/pentium/atlas/install-user.sh`
- Modificar: `.github/workflows/foundation-ci.yml`

**Interfaces:**
- Consome: todos os módulos A1.
- Produz: instalador user-level contendo A1 e marcador CI `DEVEX_HOMELAB_ATLAS_AFETIVO_A1_PASS`.

- [ ] **Passo 1: escrever o teste RED de empacotamento e CI**

Criar `test_a1_empacotamento.py`:

```python
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
ATLAS = ROOT / "infrastructure" / "pentium" / "atlas"
WORKFLOW = ROOT / ".github" / "workflows" / "foundation-ci.yml"


class A1EmpacotamentoTests(unittest.TestCase):
    def test_instalador_inclui_nucleo_afetivo_sem_ativar_servico(self):
        text = (ATLAS / "install-user.sh").read_text(encoding="utf-8")
        for required in (
            "modelo_afetivo.py",
            "configuracao_afetiva.py",
            "decaimento_afetivo.py",
            "motor_afetivo.py",
            "persistencia_afetiva.py",
            "config_afetiva.json",
        ):
            self.assertIn(required, text)
        lowered = text.lower()
        self.assertNotIn("systemctl enable", lowered)
        self.assertNotIn("systemctl start", lowered)

    def test_foundation_ci_compila_valida_e_marca_a1(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        for required in (
            "modelo_afetivo.py",
            "configuracao_afetiva.py",
            "decaimento_afetivo.py",
            "motor_afetivo.py",
            "persistencia_afetiva.py",
            "config_afetiva.json",
            "DEVEX_HOMELAB_ATLAS_AFETIVO_A1_PASS",
        ):
            self.assertIn(required, text)
```

- [ ] **Passo 2: executar e confirmar RED**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_a1_empacotamento -v
```

Resultado esperado: dois testes falham porque instalador e workflow ainda não referenciam A1.

- [ ] **Passo 3: atualizar `install-user.sh`**

No primeiro `for file in`, adicionar antes de `cli.py`:

```bash
  modelo_afetivo.py \
  configuracao_afetiva.py \
  decaimento_afetivo.py \
  motor_afetivo.py \
  persistencia_afetiva.py \
```

Alterar o loop de configuração para:

```bash
for config in config.json observation_config.json config_afetiva.json; do
  install -m 0644 "${SOURCE_DIR}/${config}" "${TARGET_DIR}/${config}"
done
```

Adicionar os cinco módulos ao `python3 -m py_compile` e validar:

```bash
python3 -m json.tool "${TARGET_DIR}/config_afetiva.json" >/dev/null
echo "ATLAS_AFETIVO_A1_INSTALL_PASS"
```

Não adicionar `systemctl`, timers ou unidade persistente.

- [ ] **Passo 4: atualizar `foundation-ci.yml`**

No gate Atlas existente, adicionar os cinco novos módulos ao `python3 -m py_compile`, adicionar:

```bash
python3 -m json.tool "$atlas/config_afetiva.json" >/dev/null
```

E, depois da suíte Atlas passar, emitir:

```bash
echo 'DEVEX_HOMELAB_ATLAS_AFETIVO_A1_PASS'
```

Manter os marcadores anteriores intactos.

- [ ] **Passo 5: confirmar GREEN e commit**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_a1_empacotamento -v
bash -n infrastructure/pentium/atlas/install-user.sh
python3 -m json.tool infrastructure/pentium/atlas/config_afetiva.json >/dev/null
python3 -m unittest discover -s infrastructure/pentium/atlas/tests -p 'test_*.py' -v
git add infrastructure/pentium/atlas/tests/test_a1_empacotamento.py infrastructure/pentium/atlas/install-user.sh .github/workflows/foundation-ci.yml
git commit -m "ci(atlas): certificar nucleo afetivo A1"
```

Resultado esperado do teste específico: `Ran 2 tests ... OK`.

---

### Tarefa 7: Gate local integral e PR Draft da A1

**Arquivos:** nenhum código novo; validação e publicação da branch.

**Interfaces:**
- Consome: tarefas 1–6 concluídas.
- Produz: HEAD de código A1 com gate local integral e PR Draft empilhada sobre Observation Runtime.

- [ ] **Passo 1: confirmar worktree limpa e ancestry correta**

```bash
git status --short
git merge-base --is-ancestor 1a28a54a051d152d83cf919a7f570e1bacccdf2e HEAD
git rev-parse HEAD
```

Resultado esperado: `git status --short` sem saída e `merge-base` exit `0`.

- [ ] **Passo 2: executar o gate integral local**

```bash
python3 -m unittest discover -s infrastructure/network/tests -p 'test_*.py' -v
python3 -m unittest discover -s infrastructure/pentium/heartbeat/tests -p 'test_*.py' -v
python3 -m unittest discover -s infrastructure/pentium/agent/tests -p 'test_*.py' -v
python3 -m unittest discover -s infrastructure/pentium/atlas/tests -p 'test_*.py' -v
bash -n infrastructure/pentium/atlas/install-user.sh
python3 -m json.tool infrastructure/pentium/atlas/config.json >/dev/null
python3 -m json.tool infrastructure/pentium/atlas/observation_config.json >/dev/null
python3 -m json.tool infrastructure/pentium/atlas/config_afetiva.json >/dev/null
git diff --check 1a28a54a051d152d83cf919a7f570e1bacccdf2e..HEAD
```

Resultado esperado: Network `6`, Heartbeat `7`, Pentium Agent `10`, Atlas `78`; total `101` testes GREEN, além de Bash/JSON/diff check PASS.

- [ ] **Passo 3: publicar a branch sem alterar configuração global de credenciais**

No x99, se o helper padrão travar, usar somente no comando:

```powershell
git -c credential.helper= -c credential.helper='!gh auth git-credential' push -u origin atlas/issue-20-motor-estado-afetivo
```

Confirmar `PUSH_EXIT=0` antes de prosseguir.

- [ ] **Passo 4: abrir PR Draft empilhada**

```bash
gh pr create \
  --repo deraldinho/devex-homelab \
  --draft \
  --base atlas/issue-20-observation-runtime \
  --head atlas/issue-20-motor-estado-afetivo \
  --title "feat(atlas): implementar A1 nucleo afetivo" \
  --body "## Objetivo\nImplementa A1 do Motor de Estado Afetivo: contratos, personalidade-base, decaimento temporal, impulsos bounded e persistência atômica.\n\n## Base\nPR #23 / atlas/issue-20-observation-runtime @ 1a28a54a051d152d83cf919a7f570e1bacccdf2e.\n\n## Limites\nSem LLM, agentes C++, transporte, diagnóstico ativo, áudio, controle remoto ou serviço persistente.\n\n/checkpoint será atualizado após CI e certificação do HEAD exato."
```

Não marcar Ready e não realizar merge.

- [ ] **Passo 5: esperar Foundation CI no HEAD exato de código**

Registrar o SHA:

```bash
CODE_SHA=$(git rev-parse HEAD)
echo "$CODE_SHA"
```

Verificar que Foundation CI terminou com `success` exatamente nesse SHA. Resultado de SHA anterior não é aceito.

---

### Tarefa 8: Certificação física bounded, as-built e checkpoint final

**Arquivos:**
- Modificar: `docs/as-built/2026-09-02-baseline.md`
- Comentário `/checkpoint` na PR A1.

**Interfaces:**
- Consome: HEAD de código local GREEN + Foundation CI `success` no mesmo SHA.
- Produz: evidência física user-level sem serviço persistente, documentação as-built e HEAD final novamente certificado por CI.

- [ ] **Passo 1: gerar pacote determinístico sem `git archive` do Windows**

Devido ao problema já comprovado de conversão CRLF em `git archive` no Windows, gerar o tar.gz diretamente dos blobs Git. O pacote deve conter somente:

```text
infrastructure/pentium/atlas/__init__.py
infrastructure/pentium/atlas/modelo_afetivo.py
infrastructure/pentium/atlas/configuracao_afetiva.py
infrastructure/pentium/atlas/config_afetiva.json
infrastructure/pentium/atlas/decaimento_afetivo.py
infrastructure/pentium/atlas/motor_afetivo.py
infrastructure/pentium/atlas/persistencia_afetiva.py
```

Usar um script Python temporário que leia cada conteúdo com `git show <CODE_SHA>:<path>`, grave tar entries com `mtime=0`, `uid=gid=0`, nomes vazios e gzip `mtime=0`. O arquivo final deve ser nomeado:

```text
atlas-a1-<CODE_SHA_CURTO>-gitblob.tar.gz
```

Calcular SHA-256 local e registrar o valor real.

- [ ] **Passo 2: transferir para diretório isolado do Pentium**

Usar o OpenSSH do Git for Windows já validado, sem alterar chaves ou `known_hosts`:

```powershell
& 'C:\Program Files\Git\usr\bin\scp.exe' -o BatchMode=yes <PACOTE> deraldinho@pentium:~/
```

No Pentium, extrair para:

```text
~/atlas-a1-cert/<CODE_SHA>/
```

Não executar `install-user.sh`; não sobrescrever `~/pentium-agent/atlas`; não criar systemd.

- [ ] **Passo 3: executar smoke físico determinístico da A1**

A partir do diretório extraído, executar com `PYTHONPATH` apontando para a raiz do pacote:

```python
from pathlib import Path
from infrastructure.pentium.atlas.configuracao_afetiva import carregar_configuracao_afetiva
from infrastructure.pentium.atlas.modelo_afetivo import ImpulsoAfetivo
from infrastructure.pentium.atlas.motor_afetivo import MotorEstadoAfetivo
from infrastructure.pentium.atlas.persistencia_afetiva import RepositorioEstadoAfetivo, restaurar_estado

raiz = Path.cwd()
atlas = raiz / "infrastructure" / "pentium" / "atlas"
cfg = carregar_configuracao_afetiva(atlas / "config_afetiva.json")
inicial = cfg.personalidade.criar_estado("2026-09-04T12:00:00+00:00")
motor = MotorEstadoAfetivo(cfg.personalidade, cfg.decaimento, inicial, lambda: "2026-09-04T12:10:00+00:00")
alterado = motor.aplicar_impulso(ImpulsoAfetivo("certificacao", delta_estresse=0.40, delta_ativacao=0.30))
assert alterado.estresse > inicial.estresse
assert alterado.ativacao > inicial.ativacao
repo = RepositorioEstadoAfetivo(raiz / "estado-afetivo-cert.json")
repo.salvar(alterado)
restaurado = restaurar_estado(repo, cfg.personalidade, cfg.decaimento, "2026-09-05T00:10:00+00:00")
assert restaurado.estado.estresse < alterado.estresse
assert restaurado.estado.estresse > cfg.personalidade.estresse
print("ATLAS_A1_PHYSICAL_SMOKE_PASS")
```

Registrar saída real, hash do pacote e confirmar que nenhum serviço, rede, SSH, Tailscale, firewall ou modem foi modificado.

- [ ] **Passo 4: atualizar o as-built somente com evidência observada**

Adicionar uma seção `Atlas Motor de Estado Afetivo — A1` contendo:

- base `1a28a54a051d152d83cf919a7f570e1bacccdf2e`;
- `CODE_SHA` real;
- contagens do gate local (`6 + 7 + 10 + 78 = 101` se exatamente essas contagens forem observadas);
- número/id/conclusão da Foundation CI do `CODE_SHA`;
- SHA-256 real do pacote gitblob;
- marcador `ATLAS_A1_PHYSICAL_SMOKE_PASS` se efetivamente emitido;
- confirmação de que a certificação foi isolada/user-level, sem instalação persistente;
- ausência de LLM, agentes C++, transporte e diagnóstico ativo nesta sub-slice;
- nenhuma afirmação de soak 24h/7d se ele não tiver ocorrido.

Se qualquer contagem ou evidência divergir, registrar o valor observado, não o esperado.

- [ ] **Passo 5: commit de documentação e gate final**

```bash
git add docs/as-built/2026-09-02-baseline.md
git commit -m "docs(atlas): registrar certificacao do nucleo afetivo A1"
git rev-parse HEAD
```

Executar novamente todo o gate da Tarefa 7 no novo HEAD documental, depois push e aguardar Foundation CI `success` exatamente no HEAD final.

- [ ] **Passo 6: publicar `/checkpoint` em pt-BR na PR**

O comentário deve conter apenas evidência confirmada:

```text
/checkpoint — Atlas Motor de Estado Afetivo A1

HEAD final: <SHA_FINAL>
Base: PR #23 @ 1a28a54a051d152d83cf919a7f570e1bacccdf2e
Estado da PR: Draft

Implementado:
- EstadoAfetivo com seis dimensões bounded;
- PersonalidadeBase versionada;
- ImpulsoAfetivo bounded;
- decaimento exponencial por meia-vida;
- atenuação offline limitada a 3600 s;
- persistência JSON atômica e fallback explícito.

Validação:
- Network: 6/6
- Heartbeat: 7/7
- Pentium Agent: 10/10
- Atlas: 78/78
- total: 101 GREEN
- bash/json/diff check: PASS
- Foundation CI: <RUN_ID>, success no SHA final exato

Certificação física:
- pacote: <NOME>
- SHA-256: <HASH>
- marcador: ATLAS_A1_PHYSICAL_SMOKE_PASS
- sem serviço persistente ou mudança de rede/SSH/Tailscale/firewall/modem

Fora de escopo confirmado:
- LLM, A2–A8, agente C++, TCP/gRPC/HTTPS, diagnóstico ativo, áudio e controle remoto.

Próximo passo seguro: A2 — Entidades, vínculos e expectativas, somente após decisão explícita.
```

Substituir campos entre `<...>` pelos valores observados; não publicar placeholders.

- [ ] **Passo 7: verificar estado final da PR**

Confirmar que a PR continua `open`, `draft=true`, `merged=false`, base `atlas/issue-20-observation-runtime` e HEAD igual ao SHA final certificado. Não marcar Ready nem mergear.

## Critérios de conclusão da A1

A1 só pode ser declarada concluída quando todos estes itens forem verdadeiros no HEAD final:

- `EstadoAfetivo`, `PersonalidadeBase`, `ImpulsoAfetivo` e `PoliticaDecaimento` implementados em pt-BR;
- baseline carregado de `config_afetiva.json` schema 1;
- decaimento exponencial determinístico por tempo absoluto;
- limite offline de `3600` s comprovado por teste;
- aplicação de impulso bounded e sem decisão de foco;
- persistência atômica com round-trip;
- snapshot ausente e corrompido retornam baseline com origem explícita;
- instalador user-level inclui A1 sem ativar serviço;
- Foundation CI compila módulos, valida JSON e executa suíte A1;
- gate local integral GREEN;
- Foundation CI `success` no HEAD final exato;
- checkpoint da PR atualizado em pt-BR;
- nenhuma implementação de A2–A8 antecipada;
- nenhuma LLM, áudio, ação remota ou mudança de infraestrutura persistente introduzida.
