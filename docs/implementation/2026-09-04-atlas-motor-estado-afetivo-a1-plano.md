# A1 — Núcleo Afetivo — Plano de Implementação

> **Para execução com agentes:** SUB-SKILL OBRIGATÓRIA: usar `superpowers:subagent-driven-development` (recomendado) ou `superpowers:executing-plans` para executar este plano tarefa por tarefa. Os passos usam caixas `- [ ]` para acompanhamento.

**Objetivo:** implementar o núcleo afetivo determinístico do Atlas com estado de seis dimensões, personalidade-base, impulsos limitados, decaimento temporal por meia-vida, persistência atômica e retomada com atenuação offline limitada.

**Arquitetura:** a A1 é uma camada pura e independente do `ObservationRuntime`: recebe `ImpulsoAfetivo` já contextualizado, aplica decaimento e atualização limitada sobre `EstadoAfetivo` e persiste estados locais. Não implementa vínculos, correlação, decisão de foco, agentes C++, transporte, diagnóstico ativo, LLM, áudio ou ações de controle.

**Stack técnica:** Python 3.14 compatível com a base atual, `dataclasses`, `datetime`, `json`, `math`, `os`, `pathlib`, `unittest`; sem dependência Python externa.

**Especificação:** `docs/implementation/2026-09-04-atlas-motor-estado-afetivo-design.md`

## Restrições globais

- Todo novo contrato, documentação, teste, mensagem e checkpoint desta sub-slice deve estar em português do Brasil; identificadores Python novos usam português sem acentos.
- Contratos legados certificados (`Stimulus`, `ObservationRuntime`, `ReactionEngine` etc.) não serão renomeados nesta sub-slice.
- O estado técnico continua autoritativo; A1 não lê nem reclassifica saúde técnica.
- A LLM não participa da A1 e o número de chamadas de LLM deve permanecer zero.
- Nenhuma alteração de rede, SSH, Tailscale, firewall, modem, rota, DNS, systemd ou serviço persistente é permitida.
- `valencia` é limitada a `-1.0..+1.0`; `ativacao`, `estresse`, `confianca`, `engajamento` e `curiosidade` são limitadas a `0.0..1.0`.
- Instantes são normalizados para UTC e armazenados como ISO-8601 com timezone.
- Decaimento usa fórmula exponencial por meia-vida e depende do tempo decorrido, não da quantidade de ciclos.
- Durante período offline, o decaimento efetivo é limitado a no máximo `3600` segundos.
- TDD é obrigatório: cada tarefa de código começa com teste RED, segue com implementação mínima GREEN e termina com commit próprio.
- A branch permanece empilhada sobre `atlas/issue-20-observation-runtime`; não marcar Ready nem realizar merge durante A1 sem decisão explícita.

## Configuração inicial da A1

`config_afetiva.json` usa `versao_esquema=1` e os seguintes valores iniciais:

```json
{
  "versao_esquema": 1,
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

Os valores são configuração versionada, não constantes de negócio dentro do motor.

## Estrutura de arquivos

- Criar `infrastructure/pentium/atlas/modelo_afetivo.py` — contratos puros.
- Criar `infrastructure/pentium/atlas/configuracao_afetiva.py` — carregamento/validação do JSON.
- Criar `infrastructure/pentium/atlas/config_afetiva.json` — personalidade e política iniciais.
- Criar `infrastructure/pentium/atlas/decaimento_afetivo.py` — decaimento puro.
- Criar `infrastructure/pentium/atlas/motor_afetivo.py` — estado em memória e impulsos.
- Criar `infrastructure/pentium/atlas/persistencia_afetiva.py` — escrita atômica e restauração.
- Criar seis arquivos de teste A1 sob `infrastructure/pentium/atlas/tests/`.
- Modificar `infrastructure/pentium/atlas/install-user.sh` e `.github/workflows/foundation-ci.yml`.
- Modificar `docs/as-built/2026-09-02-baseline.md` somente depois da certificação.

## Preparação da worktree existente

A worktree já existe em `C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-affective`; não criar outra. Quando o x99 estiver online:

```powershell
Set-Location 'C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-affective'
git status --short
git fetch origin atlas/issue-20-motor-estado-afetivo
```

Se o design aparecer como arquivo não rastreado, comparar o blob local com o remoto sem conversão de fim de linha:

```powershell
$Design = 'docs/implementation/2026-09-04-atlas-motor-estado-afetivo-design.md'
$LocalBlob = (git hash-object --no-filters $Design).Trim()
$RemoteBlob = (git rev-parse "origin/atlas/issue-20-motor-estado-afetivo:$Design").Trim()
Write-Output "LOCAL_BLOB=$LocalBlob"
Write-Output "REMOTE_BLOB=$RemoteBlob"
if ($LocalBlob -eq $RemoteBlob) {
    Remove-Item $Design
} else {
    Move-Item $Design (Join-Path $env:TEMP 'atlas-design-local-backup.md') -Force
}
git merge --ff-only origin/atlas/issue-20-motor-estado-afetivo
if ($LASTEXITCODE -ne 0) { throw 'fast-forward da worktree falhou' }
git status --short
git rev-parse HEAD
```

A worktree deve estar limpa antes do primeiro RED.

---

### Tarefa 1: Contratos puros do núcleo afetivo

**Arquivos:**
- Criar `infrastructure/pentium/atlas/modelo_afetivo.py`.
- Criar `infrastructure/pentium/atlas/tests/test_modelo_afetivo.py`.

**Interfaces produzidas:**
- `EstadoAfetivo`;
- `PersonalidadeBase`;
- `ImpulsoAfetivo`;
- `PoliticaDecaimento`.

- [ ] **Passo 1: escrever o teste RED**

```python
import unittest

from infrastructure.pentium.atlas.modelo_afetivo import EstadoAfetivo, ImpulsoAfetivo, PersonalidadeBase


class ModeloAfetivoTests(unittest.TestCase):
    def test_estado_limita_dimensoes(self):
        estado = EstadoAfetivo(2.0, 1.5, -0.4, 1.2, -1.0, 0.6, "2026-09-04T12:00:00+00:00")
        self.assertEqual((1.0, 1.0, 0.0, 1.0, 0.0, 0.6), (
            estado.valencia, estado.ativacao, estado.estresse,
            estado.confianca, estado.engajamento, estado.curiosidade,
        ))

    def test_impulso_rejeita_delta_fora_do_intervalo(self):
        with self.assertRaises(ValueError):
            ImpulsoAfetivo("teste", delta_estresse=1.01)

    def test_personalidade_cria_estado_na_base(self):
        personalidade = PersonalidadeBase(0.20, 0.25, 0.10, 0.70, 0.55, 0.75)
        estado = personalidade.criar_estado("2026-09-04T12:00:00+00:00")
        self.assertEqual(0.20, estado.valencia)
        self.assertEqual(0.10, estado.estresse)
        self.assertEqual(0.75, estado.curiosidade)
        self.assertIsNone(estado.foco_atencao)

    def test_instante_com_offset_e_normalizado_para_utc(self):
        personalidade = PersonalidadeBase(0.20, 0.25, 0.10, 0.70, 0.55, 0.75)
        estado = personalidade.criar_estado("2026-09-04T09:00:00-03:00")
        self.assertEqual("2026-09-04T12:00:00+00:00", estado.atualizado_em)
```

- [ ] **Passo 2: confirmar RED**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_modelo_afetivo -v
```

Esperado: importação falha porque `modelo_afetivo.py` não existe.

- [ ] **Passo 3: implementar o modelo mínimo**

```python
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone


def _finito(valor: float, nome: str) -> float:
    numero = float(valor)
    if not math.isfinite(numero):
        raise ValueError(f"{nome} deve ser finito")
    return numero


def _limitar(valor: float, minimo: float, maximo: float, nome: str) -> float:
    return max(minimo, min(maximo, _finito(valor, nome)))


def _validar_intervalo(valor: float, minimo: float, maximo: float, nome: str) -> float:
    numero = _finito(valor, nome)
    if not minimo <= numero <= maximo:
        raise ValueError(f"{nome} deve estar entre {minimo} e {maximo}")
    return numero


def _normalizar_instante_utc(valor: str) -> str:
    instante = datetime.fromisoformat(valor)
    if instante.tzinfo is None or instante.utcoffset() is None:
        raise ValueError("atualizado_em deve possuir timezone")
    return instante.astimezone(timezone.utc).isoformat()


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
        object.__setattr__(self, "atualizado_em", _normalizar_instante_utc(self.atualizado_em))


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
            self.valencia, self.ativacao, self.estresse,
            self.confianca, self.engajamento, self.curiosidade,
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
        if not isinstance(self.motivo, str) or not self.motivo.strip():
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
            numero = _finito(getattr(self, nome), nome)
            if numero <= 0:
                raise ValueError(f"{nome} deve ser > 0")
            object.__setattr__(self, nome, numero)
        offline = _finito(self.atenuacao_offline_maxima_s, "atenuacao_offline_maxima_s")
        if offline < 0:
            raise ValueError("atenuacao_offline_maxima_s deve ser >= 0")
        object.__setattr__(self, "atenuacao_offline_maxima_s", offline)
```

- [ ] **Passo 4: confirmar GREEN e commit**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_modelo_afetivo -v
python3 -m unittest discover -s infrastructure/pentium/atlas/tests -p 'test_*.py' -v
git add infrastructure/pentium/atlas/modelo_afetivo.py infrastructure/pentium/atlas/tests/test_modelo_afetivo.py
git commit -m "feat(atlas): adicionar contratos do nucleo afetivo"
```

Teste específico esperado: `Ran 4 tests ... OK`.

---

### Tarefa 2: Configuração versionada

**Arquivos:**
- Criar `infrastructure/pentium/atlas/configuracao_afetiva.py`.
- Criar `infrastructure/pentium/atlas/config_afetiva.json` com o JSON exato da seção de configuração inicial.
- Criar `infrastructure/pentium/atlas/tests/test_configuracao_afetiva.py`.

**Interfaces produzidas:** `ConfiguracaoAfetiva` e `carregar_configuracao_afetiva(path)`.

- [ ] **Passo 1: escrever o teste RED**

```python
import json
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.configuracao_afetiva import carregar_configuracao_afetiva


ROOT = Path(__file__).resolve().parents[4]
CONFIG = ROOT / "infrastructure" / "pentium" / "atlas" / "config_afetiva.json"


class ConfiguracaoAfetivaTests(unittest.TestCase):
    def test_configuracao_do_repositorio_carrega_valores_canonicos(self):
        cfg = carregar_configuracao_afetiva(CONFIG)
        self.assertEqual(0.20, cfg.personalidade.valencia)
        self.assertEqual(0.10, cfg.personalidade.estresse)
        self.assertEqual(0.75, cfg.personalidade.curiosidade)
        self.assertEqual(900.0, cfg.decaimento.meia_vida_ativacao_s)
        self.assertEqual(3600.0, cfg.decaimento.atenuacao_offline_maxima_s)

    def test_versao_de_esquema_diferente_de_um_e_rejeitada(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({"versao_esquema": 2}), encoding="utf-8")
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

- [ ] **Passo 2: confirmar RED**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_configuracao_afetiva -v
```

Esperado: importação falha.

- [ ] **Passo 3: implementar o carregador**

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
    if payload.get("versao_esquema") != 1:
        raise ValueError("config afetiva versao_esquema deve ser 1")
    try:
        personalidade = PersonalidadeBase(**payload["personalidade_base"])
        decaimento = PoliticaDecaimento(**payload["decaimento"])
    except KeyError as exc:
        raise ValueError(f"config afetiva sem campo obrigatório: {exc.args[0]}") from exc
    return ConfiguracaoAfetiva(personalidade, decaimento)
```

- [ ] **Passo 4: confirmar GREEN, JSON válido e commit**

```bash
python3 -m json.tool infrastructure/pentium/atlas/config_afetiva.json >/dev/null
python3 -m unittest infrastructure.pentium.atlas.tests.test_configuracao_afetiva -v
python3 -m unittest discover -s infrastructure/pentium/atlas/tests -p 'test_*.py' -v
git add infrastructure/pentium/atlas/configuracao_afetiva.py infrastructure/pentium/atlas/config_afetiva.json infrastructure/pentium/atlas/tests/test_configuracao_afetiva.py
git commit -m "feat(atlas): configurar personalidade e decaimento afetivo"
```

Teste específico esperado: `Ran 3 tests ... OK`.

---

### Tarefa 3: Decaimento temporal determinístico

**Arquivos:** criar `decaimento_afetivo.py` e `test_decaimento_afetivo.py`.

**Interface produzida:** `decair_estado(estado, personalidade, politica, agora, modo_offline=False)`.

Fórmula canônica:

```text
novo = base + (atual - base) * 0.5 ** (segundos_efetivos / meia_vida)
```

- [ ] **Passo 1: escrever o teste RED**

```python
import unittest

from infrastructure.pentium.atlas.decaimento_afetivo import decair_estado
from infrastructure.pentium.atlas.modelo_afetivo import EstadoAfetivo, PersonalidadeBase, PoliticaDecaimento


P = PersonalidadeBase(0.20, 0.25, 0.10, 0.70, 0.55, 0.75)
D = PoliticaDecaimento(3600, 900, 1800, 21600, 7200, 10800, 3600)


class DecaimentoAfetivoTests(unittest.TestCase):
    def test_uma_meia_vida_reduz_metade_da_distancia_ate_a_base(self):
        estado = EstadoAfetivo(0.80, 0.25, 0.10, 0.70, 0.55, 0.75, "2026-09-04T12:00:00+00:00")
        novo = decair_estado(estado, P, D, "2026-09-04T13:00:00+00:00")
        self.assertAlmostEqual(0.50, novo.valencia, places=9)

    def test_modo_offline_limita_decaimento_a_uma_hora(self):
        estado = EstadoAfetivo(0.80, 0.25, 0.10, 0.70, 0.55, 0.75, "2026-09-04T00:00:00+00:00")
        novo = decair_estado(estado, P, D, "2026-09-04T12:00:00+00:00", modo_offline=True)
        self.assertAlmostEqual(0.50, novo.valencia, places=9)
        self.assertEqual("2026-09-04T12:00:00+00:00", novo.atualizado_em)

    def test_instante_anterior_ao_estado_e_rejeitado(self):
        with self.assertRaises(ValueError):
            decair_estado(P.criar_estado("2026-09-04T12:00:00+00:00"), P, D, "2026-09-04T11:59:59+00:00")
```

- [ ] **Passo 2: confirmar RED**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_decaimento_afetivo -v
```

- [ ] **Passo 3: implementar**

```python
from __future__ import annotations

from datetime import datetime

from .modelo_afetivo import EstadoAfetivo, PersonalidadeBase, PoliticaDecaimento


def _aproximar(atual: float, base: float, meia_vida_s: float, segundos: float) -> float:
    return base + (atual - base) * (0.5 ** (segundos / meia_vida_s))


def decair_estado(
    estado: EstadoAfetivo,
    personalidade: PersonalidadeBase,
    politica: PoliticaDecaimento,
    agora: str,
    *,
    modo_offline: bool = False,
) -> EstadoAfetivo:
    instante = personalidade.criar_estado(agora).atualizado_em
    decorridos = (datetime.fromisoformat(instante) - datetime.fromisoformat(estado.atualizado_em)).total_seconds()
    if decorridos < 0:
        raise ValueError("agora não pode ser anterior ao estado")
    efetivos = min(decorridos, politica.atenuacao_offline_maxima_s) if modo_offline else decorridos
    return EstadoAfetivo(
        _aproximar(estado.valencia, personalidade.valencia, politica.meia_vida_valencia_s, efetivos),
        _aproximar(estado.ativacao, personalidade.ativacao, politica.meia_vida_ativacao_s, efetivos),
        _aproximar(estado.estresse, personalidade.estresse, politica.meia_vida_estresse_s, efetivos),
        _aproximar(estado.confianca, personalidade.confianca, politica.meia_vida_confianca_s, efetivos),
        _aproximar(estado.engajamento, personalidade.engajamento, politica.meia_vida_engajamento_s, efetivos),
        _aproximar(estado.curiosidade, personalidade.curiosidade, politica.meia_vida_curiosidade_s, efetivos),
        instante,
        estado.foco_atencao,
    )
```

- [ ] **Passo 4: confirmar GREEN e commit**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_decaimento_afetivo -v
python3 -m unittest discover -s infrastructure/pentium/atlas/tests -p 'test_*.py' -v
git add infrastructure/pentium/atlas/decaimento_afetivo.py infrastructure/pentium/atlas/tests/test_decaimento_afetivo.py
git commit -m "feat(atlas): adicionar decaimento temporal afetivo"
```

Teste específico esperado: `Ran 3 tests ... OK`.

---

### Tarefa 4: Motor em memória e impulsos

**Arquivos:** criar `motor_afetivo.py` e `test_motor_afetivo.py`.

**Interfaces produzidas:** `MotorEstadoAfetivo.estado_atual`, `decair_ate()` e `aplicar_impulso()`.

- [ ] **Passo 1: escrever o teste RED**

```python
import unittest

from infrastructure.pentium.atlas.modelo_afetivo import EstadoAfetivo, ImpulsoAfetivo, PersonalidadeBase, PoliticaDecaimento
from infrastructure.pentium.atlas.motor_afetivo import MotorEstadoAfetivo


P = PersonalidadeBase(0.20, 0.25, 0.10, 0.70, 0.55, 0.75)
D = PoliticaDecaimento(3600, 900, 1800, 21600, 7200, 10800, 3600)


class MotorEstadoAfetivoTests(unittest.TestCase):
    def test_impulso_aplica_decaimento_antes_do_delta(self):
        inicial = EstadoAfetivo(0.80, 0.25, 0.10, 0.70, 0.55, 0.75, "2026-09-04T12:00:00+00:00")
        motor = MotorEstadoAfetivo(P, D, inicial, lambda: "2026-09-04T13:00:00+00:00")
        novo = motor.aplicar_impulso(ImpulsoAfetivo("recuperacao", delta_valencia=0.10))
        self.assertAlmostEqual(0.60, novo.valencia, places=9)

    def test_impulso_respeita_limites(self):
        motor = MotorEstadoAfetivo(P, D, P.criar_estado("2026-09-04T12:00:00+00:00"), lambda: "2026-09-04T12:00:00+00:00")
        novo = motor.aplicar_impulso(ImpulsoAfetivo("critico", delta_estresse=1.0, delta_ativacao=1.0))
        self.assertEqual(1.0, novo.estresse)
        self.assertEqual(1.0, novo.ativacao)

    def test_a1_preserva_foco_sem_decidi_lo(self):
        inicial = EstadoAfetivo(0.20, 0.25, 0.10, 0.70, 0.55, 0.75, "2026-09-04T12:00:00+00:00", "x99")
        motor = MotorEstadoAfetivo(P, D, inicial, lambda: "2026-09-04T12:00:00+00:00")
        self.assertEqual("x99", motor.aplicar_impulso(ImpulsoAfetivo("teste", delta_curiosidade=0.10)).foco_atencao)
```

- [ ] **Passo 2: confirmar RED**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_motor_afetivo -v
```

- [ ] **Passo 3: implementar**

```python
from __future__ import annotations

from collections.abc import Callable

from .decaimento_afetivo import decair_estado
from .modelo_afetivo import EstadoAfetivo, ImpulsoAfetivo, PersonalidadeBase, PoliticaDecaimento


class MotorEstadoAfetivo:
    def __init__(self, personalidade: PersonalidadeBase, politica: PoliticaDecaimento, estado_inicial: EstadoAfetivo, relogio: Callable[[], str]):
        self._personalidade = personalidade
        self._politica = politica
        self._estado = estado_inicial
        self._relogio = relogio

    @property
    def estado_atual(self) -> EstadoAfetivo:
        return self._estado

    def decair_ate(self, agora: str | None = None, *, modo_offline: bool = False) -> EstadoAfetivo:
        instante = agora or self._relogio()
        self._estado = decair_estado(self._estado, self._personalidade, self._politica, instante, modo_offline=modo_offline)
        return self._estado

    def aplicar_impulso(self, impulso: ImpulsoAfetivo, ocorrido_em: str | None = None) -> EstadoAfetivo:
        instante = ocorrido_em or self._relogio()
        base = self.decair_ate(instante)
        self._estado = EstadoAfetivo(
            base.valencia + impulso.delta_valencia,
            base.ativacao + impulso.delta_ativacao,
            base.estresse + impulso.delta_estresse,
            base.confianca + impulso.delta_confianca,
            base.engajamento + impulso.delta_engajamento,
            base.curiosidade + impulso.delta_curiosidade,
            instante,
            base.foco_atencao,
        )
        return self._estado
```

- [ ] **Passo 4: confirmar GREEN e commit**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_motor_afetivo -v
python3 -m unittest discover -s infrastructure/pentium/atlas/tests -p 'test_*.py' -v
git add infrastructure/pentium/atlas/motor_afetivo.py infrastructure/pentium/atlas/tests/test_motor_afetivo.py
git commit -m "feat(atlas): implementar motor de estado afetivo A1"
```

Teste específico esperado: `Ran 3 tests ... OK`.

---

### Tarefa 5: Persistência atômica e restauração segura

**Arquivos:** criar `persistencia_afetiva.py` e `test_persistencia_afetiva.py`.

**Interfaces produzidas:** `EstadoAfetivoSalvoInvalido`, `OrigemRestauracaoAfetiva`, `ResultadoRestauracaoAfetiva`, `RepositorioEstadoAfetivo`, `restaurar_estado()`.

- [ ] **Passo 1: escrever o teste RED**

```python
import json
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.modelo_afetivo import EstadoAfetivo, PersonalidadeBase, PoliticaDecaimento
from infrastructure.pentium.atlas.persistencia_afetiva import OrigemRestauracaoAfetiva, RepositorioEstadoAfetivo, restaurar_estado


P = PersonalidadeBase(0.20, 0.25, 0.10, 0.70, 0.55, 0.75)
D = PoliticaDecaimento(3600, 900, 1800, 21600, 7200, 10800, 3600)


class PersistenciaAfetivaTests(unittest.TestCase):
    def test_salvar_e_carregar_preserva_estado(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = RepositorioEstadoAfetivo(Path(tmp) / "estado.json")
            estado = EstadoAfetivo(0.40, 0.60, 0.80, 0.50, 0.70, 0.90, "2026-09-04T12:00:00+00:00", "core")
            repo.salvar(estado)
            self.assertEqual(estado, repo.carregar())
            self.assertFalse((Path(tmp) / "estado.json.tmp").exists())

    def test_arquivo_corrompido_retorna_base_com_erro(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "estado.json"
            path.write_text("{quebrado", encoding="utf-8")
            resultado = restaurar_estado(RepositorioEstadoAfetivo(path), P, D, "2026-09-04T12:00:00+00:00")
            self.assertEqual(OrigemRestauracaoAfetiva.BASE_POR_ESTADO_INVALIDO, resultado.origem)
            self.assertIsNotNone(resultado.erro)

    def test_arquivo_ausente_retorna_base_sem_erro(self):
        with tempfile.TemporaryDirectory() as tmp:
            resultado = restaurar_estado(RepositorioEstadoAfetivo(Path(tmp) / "estado.json"), P, D, "2026-09-04T12:00:00+00:00")
            self.assertEqual(OrigemRestauracaoAfetiva.BASE_POR_AUSENCIA, resultado.origem)
            self.assertIsNone(resultado.erro)

    def test_restauracao_limita_atenuacao_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = RepositorioEstadoAfetivo(Path(tmp) / "estado.json")
            repo.salvar(EstadoAfetivo(0.80, 0.25, 0.10, 0.70, 0.55, 0.75, "2026-09-04T00:00:00+00:00"))
            resultado = restaurar_estado(repo, P, D, "2026-09-04T12:00:00+00:00")
            self.assertEqual(OrigemRestauracaoAfetiva.ESTADO_SALVO, resultado.origem)
            self.assertAlmostEqual(0.50, resultado.estado.valencia, places=9)

    def test_timestamp_futuro_do_estado_salvo_nao_bloqueia_retomada(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "estado.json"
            path.write_text(json.dumps({
                "versao_esquema": 1,
                "estado": {
                    "valencia": 0.8, "ativacao": 0.25, "estresse": 0.1,
                    "confianca": 0.7, "engajamento": 0.55, "curiosidade": 0.75,
                    "atualizado_em": "2026-09-05T12:00:00+00:00", "foco_atencao": None,
                },
            }), encoding="utf-8")
            resultado = restaurar_estado(RepositorioEstadoAfetivo(path), P, D, "2026-09-04T12:00:00+00:00")
            self.assertEqual(OrigemRestauracaoAfetiva.BASE_POR_ESTADO_INVALIDO, resultado.origem)
            self.assertIsNotNone(resultado.erro)
```

- [ ] **Passo 2: confirmar RED**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_persistencia_afetiva -v
```

- [ ] **Passo 3: implementar**

```python
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .decaimento_afetivo import decair_estado
from .modelo_afetivo import EstadoAfetivo, PersonalidadeBase, PoliticaDecaimento


class EstadoAfetivoSalvoInvalido(ValueError):
    pass


class OrigemRestauracaoAfetiva(str, Enum):
    ESTADO_SALVO = "estado_salvo"
    BASE_POR_AUSENCIA = "base_por_ausencia"
    BASE_POR_ESTADO_INVALIDO = "base_por_estado_invalido"


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
            "versao_esquema": 1,
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
            if os.name == "posix" and hasattr(os, "O_DIRECTORY"):
                fd = os.open(self._caminho.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
        finally:
            temporario.unlink(missing_ok=True)

    def carregar(self) -> EstadoAfetivo | None:
        if not self._caminho.exists():
            return None
        try:
            payload = json.loads(self._caminho.read_text(encoding="utf-8"))
            if payload.get("versao_esquema") != 1:
                raise ValueError("estado afetivo versao_esquema deve ser 1")
            return EstadoAfetivo(**payload["estado"])
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise EstadoAfetivoSalvoInvalido(str(exc)) from exc


def restaurar_estado(repositorio: RepositorioEstadoAfetivo, personalidade: PersonalidadeBase, politica: PoliticaDecaimento, agora: str) -> ResultadoRestauracaoAfetiva:
    try:
        estado = repositorio.carregar()
        if estado is None:
            return ResultadoRestauracaoAfetiva(personalidade.criar_estado(agora), OrigemRestauracaoAfetiva.BASE_POR_AUSENCIA)
        restaurado = decair_estado(estado, personalidade, politica, agora, modo_offline=True)
        return ResultadoRestauracaoAfetiva(restaurado, OrigemRestauracaoAfetiva.ESTADO_SALVO)
    except (EstadoAfetivoSalvoInvalido, ValueError) as exc:
        return ResultadoRestauracaoAfetiva(
            personalidade.criar_estado(agora),
            OrigemRestauracaoAfetiva.BASE_POR_ESTADO_INVALIDO,
            str(exc),
        )
```

- [ ] **Passo 4: confirmar GREEN e commit**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_persistencia_afetiva -v
python3 -m unittest discover -s infrastructure/pentium/atlas/tests -p 'test_*.py' -v
git add infrastructure/pentium/atlas/persistencia_afetiva.py infrastructure/pentium/atlas/tests/test_persistencia_afetiva.py
git commit -m "feat(atlas): persistir estado afetivo com retomada segura"
```

Teste específico esperado: `Ran 5 tests ... OK`.

---

### Tarefa 6: Empacotamento e Foundation CI

**Arquivos:** criar `test_a1_empacotamento.py`; modificar `install-user.sh` e `.github/workflows/foundation-ci.yml`.

- [ ] **Passo 1: escrever o teste RED**

```python
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
ATLAS = ROOT / "infrastructure" / "pentium" / "atlas"
WORKFLOW = ROOT / ".github" / "workflows" / "foundation-ci.yml"


class A1EmpacotamentoTests(unittest.TestCase):
    def test_instalador_inclui_a1_sem_ativar_servico(self):
        texto = (ATLAS / "install-user.sh").read_text(encoding="utf-8")
        for obrigatorio in (
            "modelo_afetivo.py", "configuracao_afetiva.py", "decaimento_afetivo.py",
            "motor_afetivo.py", "persistencia_afetiva.py", "config_afetiva.json",
        ):
            self.assertIn(obrigatorio, texto)
        self.assertNotIn("systemctl enable", texto.lower())
        self.assertNotIn("systemctl start", texto.lower())

    def test_ci_compila_valida_e_marca_a1(self):
        texto = WORKFLOW.read_text(encoding="utf-8")
        for obrigatorio in (
            "modelo_afetivo.py", "configuracao_afetiva.py", "decaimento_afetivo.py",
            "motor_afetivo.py", "persistencia_afetiva.py", "config_afetiva.json",
            "DEVEX_HOMELAB_ATLAS_AFETIVO_A1_PASS",
        ):
            self.assertIn(obrigatorio, texto)
```

- [ ] **Passo 2: confirmar RED**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_a1_empacotamento -v
```

Esperado: dois testes falham.

- [ ] **Passo 3: modificar o instalador**

Adicionar ao `for file in`:

```bash
  modelo_afetivo.py \
  configuracao_afetiva.py \
  decaimento_afetivo.py \
  motor_afetivo.py \
  persistencia_afetiva.py \
```

Alterar a lista de configurações para:

```bash
for config in config.json observation_config.json config_afetiva.json; do
  install -m 0644 "${SOURCE_DIR}/${config}" "${TARGET_DIR}/${config}"
done
```

Adicionar os cinco módulos ao `python3 -m py_compile`, validar `config_afetiva.json` e emitir:

```bash
python3 -m json.tool "${TARGET_DIR}/config_afetiva.json" >/dev/null
echo "ATLAS_AFETIVO_A1_INSTALL_PASS"
```

- [ ] **Passo 4: modificar Foundation CI**

No gate Atlas existente, adicionar os cinco módulos ao `python3 -m py_compile`, adicionar:

```bash
python3 -m json.tool "$atlas/config_afetiva.json" >/dev/null
```

E emitir depois da suíte Atlas:

```bash
echo 'DEVEX_HOMELAB_ATLAS_AFETIVO_A1_PASS'
```

- [ ] **Passo 5: confirmar GREEN e commit**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_a1_empacotamento -v
bash -n infrastructure/pentium/atlas/install-user.sh
python3 -m json.tool infrastructure/pentium/atlas/config_afetiva.json >/dev/null
python3 -m unittest discover -s infrastructure/pentium/atlas/tests -p 'test_*.py' -v
git add infrastructure/pentium/atlas/tests/test_a1_empacotamento.py infrastructure/pentium/atlas/install-user.sh .github/workflows/foundation-ci.yml
git commit -m "ci(atlas): certificar nucleo afetivo A1"
```

Teste específico esperado: `Ran 2 tests ... OK`.

---

### Tarefa 7: Gate integral, push e PR Draft

- [ ] **Passo 1: validar ancestralidade e árvore limpa**

```bash
git status --short
git merge-base --is-ancestor 1a28a54a051d152d83cf919a7f570e1bacccdf2e HEAD
git rev-parse HEAD
```

- [ ] **Passo 2: executar o gate integral**

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

Contagem esperada: Network `6`, Heartbeat `7`, Pentium Agent `10`, Atlas `80`; total `103` GREEN. Se a contagem real divergir, investigar antes de usar qualquer número em documentação/checkpoint.

- [ ] **Passo 3: push sem persistir helper de credencial**

```powershell
git -c credential.helper= -c credential.helper='!gh auth git-credential' push -u origin atlas/issue-20-motor-estado-afetivo
if ($LASTEXITCODE -ne 0) { throw 'push falhou' }
```

- [ ] **Passo 4: abrir PR Draft empilhada**

```bash
gh pr create \
  --repo deraldinho/devex-homelab \
  --draft \
  --base atlas/issue-20-observation-runtime \
  --head atlas/issue-20-motor-estado-afetivo \
  --title "feat(atlas): implementar A1 nucleo afetivo" \
  --body "## Objetivo\nImplementa A1 do Motor de Estado Afetivo: contratos, personalidade-base, decaimento temporal, impulsos limitados e persistência atômica.\n\n## Base\nPR #23 / atlas/issue-20-observation-runtime @ 1a28a54a051d152d83cf919a7f570e1bacccdf2e.\n\n## Limites\nSem LLM, agentes C++, transporte, diagnóstico ativo, áudio, controle remoto ou serviço persistente.\n\n/checkpoint será atualizado após CI e certificação do HEAD exato."
```

Não marcar Ready e não realizar merge.

- [ ] **Passo 5: confirmar Foundation CI no HEAD de código**

```powershell
$CodeSha = (git rev-parse HEAD).Trim()
$Runs = gh run list --repo deraldinho/devex-homelab --workflow foundation-ci.yml --commit $CodeSha --limit 1 --json databaseId,headSha,status,conclusion | ConvertFrom-Json
$CodeRun = @($Runs)[0]
$CodeRun | ConvertTo-Json -Depth 4
if ($CodeRun.headSha -ne $CodeSha -or $CodeRun.status -ne 'completed' -or $CodeRun.conclusion -ne 'success') { throw 'CI do HEAD de código ainda não está GREEN' }
```

---

### Tarefa 8: Certificação física limitada, as-built e checkpoint

A certificação é isolada no diretório do usuário no Pentium. Não executar `install-user.sh`, não sobrescrever `~/pentium-agent/atlas` e não criar serviço persistente.

- [ ] **Passo 1: construir pacote determinístico a partir dos blobs Git**

No x99:

```powershell
$CodeSha = (git rev-parse HEAD).Trim()
$ShortSha = $CodeSha.Substring(0,7)
$Builder = Join-Path $env:TEMP 'construir-pacote-atlas-a1.py'
$Package = Join-Path $env:TEMP "atlas-a1-$ShortSha-gitblob.tar.gz"
```

Criar `$Builder` com:

```python
import gzip
import io
import os
import subprocess
import tarfile
from pathlib import Path

sha = os.environ["ATLAS_A1_SHA"]
saida = Path(os.environ["ATLAS_A1_PACOTE"])
arquivos = [
    "infrastructure/pentium/atlas/__init__.py",
    "infrastructure/pentium/atlas/modelo_afetivo.py",
    "infrastructure/pentium/atlas/configuracao_afetiva.py",
    "infrastructure/pentium/atlas/config_afetiva.json",
    "infrastructure/pentium/atlas/decaimento_afetivo.py",
    "infrastructure/pentium/atlas/motor_afetivo.py",
    "infrastructure/pentium/atlas/persistencia_afetiva.py",
]

with saida.open("wb") as bruto:
    with gzip.GzipFile(filename="", mode="wb", fileobj=bruto, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as tar:
            for caminho in arquivos:
                conteudo = subprocess.check_output(["git", "show", f"{sha}:{caminho}"])
                info = tarfile.TarInfo(caminho)
                info.size = len(conteudo)
                info.mode = 0o644
                info.mtime = 0
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                tar.addfile(info, io.BytesIO(conteudo))
```

Executar:

```powershell
$env:ATLAS_A1_SHA = $CodeSha
$env:ATLAS_A1_PACOTE = $Package
python $Builder
if ($LASTEXITCODE -ne 0) { throw 'construção do pacote falhou' }
$PackageSha = (Get-FileHash $Package -Algorithm SHA256).Hash.ToLowerInvariant()
$PackageName = Split-Path $Package -Leaf
Write-Output "PACOTE=$PackageName"
Write-Output "SHA256=$PackageSha"
```

Não usar `git archive` no Windows.

- [ ] **Passo 2: criar o certificador físico**

```powershell
$Smoke = Join-Path $env:TEMP 'certificar-atlas-a1.py'
```

Conteúdo de `$Smoke`:

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

- [ ] **Passo 3: transferir e conferir hash no Pentium**

```powershell
$Scp = 'C:\Program Files\Git\usr\bin\scp.exe'
$Ssh = 'C:\Program Files\Git\usr\bin\ssh.exe'
& $Scp -o BatchMode=yes $Package $Smoke deraldinho@pentium:~/
if ($LASTEXITCODE -ne 0) { throw 'transferência para Pentium falhou' }
$RemoteHashLine = & $Ssh -o BatchMode=yes deraldinho@pentium "sha256sum ~/$PackageName"
$RemoteHash = ($RemoteHashLine -split '\s+')[0].Trim().ToLowerInvariant()
if ($RemoteHash -ne $PackageSha) { throw 'hash remoto diverge do pacote local' }
```

Usar somente o hostname `pentium` já validado. Não alterar `known_hosts`, chaves ou configuração SSH.

- [ ] **Passo 4: executar certificação isolada**

```powershell
$RemoteRoot = "`$HOME/atlas-a1-cert/$CodeSha"
$RemoteCommand = "set -euo pipefail; mkdir -p $RemoteRoot; tar -xzf `"`$HOME/$PackageName`" -C $RemoteRoot; cp `"`$HOME/certificar-atlas-a1.py`" $RemoteRoot/; cd $RemoteRoot; PYTHONPATH=. python3 certificar-atlas-a1.py"
$SmokeOutput = @(& $Ssh -o BatchMode=yes deraldinho@pentium $RemoteCommand)
$SmokeOutput
if ($SmokeOutput -notcontains 'ATLAS_A1_PHYSICAL_SMOKE_PASS') { throw 'certificação física A1 falhou' }
```

- [ ] **Passo 5: capturar evidência real e atualizar as-built**

```powershell
$PrRows = gh pr list --repo deraldinho/devex-homelab --head atlas/issue-20-motor-estado-afetivo --state open --limit 1 --json number | ConvertFrom-Json
$PrNumber = [int]@($PrRows)[0].number
Write-Output "PR=$PrNumber"
Write-Output "CODE_SHA=$CodeSha"
Write-Output "CI_ID=$($CodeRun.databaseId)"
Write-Output "PACOTE=$PackageName"
Write-Output "SHA256=$PackageSha"
```

Adicionar ao `docs/as-built/2026-09-02-baseline.md` uma seção `Atlas Motor de Estado Afetivo — A1` contendo apenas valores efetivamente observados: base, `CodeSha`, contagens do gate, id/conclusão da CI do código, nome/hash do pacote, marcador `ATLAS_A1_PHYSICAL_SMOKE_PASS`, execução isolada e ausência de serviço persistente ou mudança de rede/SSH/Tailscale/firewall/modem. Não afirmar soak 24h/7d.

- [ ] **Passo 6: commit documental e gate final**

```bash
git add docs/as-built/2026-09-02-baseline.md
git commit -m "docs(atlas): registrar certificacao do nucleo afetivo A1"
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

Depois:

```powershell
git -c credential.helper= -c credential.helper='!gh auth git-credential' push origin atlas/issue-20-motor-estado-afetivo
if ($LASTEXITCODE -ne 0) { throw 'push final falhou' }
$FinalSha = (git rev-parse HEAD).Trim()
$FinalRows = gh run list --repo deraldinho/devex-homelab --workflow foundation-ci.yml --commit $FinalSha --limit 1 --json databaseId,headSha,status,conclusion | ConvertFrom-Json
$FinalRun = @($FinalRows)[0]
if ($FinalRun.headSha -ne $FinalSha -or $FinalRun.status -ne 'completed' -or $FinalRun.conclusion -ne 'success') { throw 'CI final do HEAD exato não está GREEN' }
```

- [ ] **Passo 7: publicar checkpoint em pt-BR com variáveis reais**

```powershell
$PrRows = gh pr list --repo deraldinho/devex-homelab --head atlas/issue-20-motor-estado-afetivo --state open --limit 1 --json number | ConvertFrom-Json
$PrNumber = [int]@($PrRows)[0].number
$Checkpoint = @"
/checkpoint — Atlas Motor de Estado Afetivo A1

HEAD final: $FinalSha
Base: PR #23 @ 1a28a54a051d152d83cf919a7f570e1bacccdf2e
Estado da PR: Draft

Implementado:
- EstadoAfetivo com seis dimensões limitadas;
- PersonalidadeBase versionada;
- ImpulsoAfetivo limitado;
- decaimento exponencial por meia-vida;
- atenuação offline limitada a 3600 s;
- persistência JSON atômica e retorno seguro à base.

Validação confirmada antes deste comentário:
- Network: 6/6
- Heartbeat: 7/7
- Pentium Agent: 10/10
- Atlas: 80/80
- total: 103 GREEN
- bash/json/diff check: PASS
- Foundation CI final: $($FinalRun.databaseId), success no SHA final exato

Certificação física:
- pacote: $PackageName
- SHA-256: $PackageSha
- marcador: ATLAS_A1_PHYSICAL_SMOKE_PASS
- execução isolada no Pentium, sem serviço persistente ou mudança de rede/SSH/Tailscale/firewall/modem

Fora de escopo confirmado:
- LLM, A2–A8, agente C++, TCP/gRPC/HTTPS, diagnóstico ativo, áudio e controle remoto.

Próximo passo seguro: A2 — Entidades, vínculos e expectativas, somente após decisão explícita.
"@
gh pr comment $PrNumber --repo deraldinho/devex-homelab --body $Checkpoint
if ($LASTEXITCODE -ne 0) { throw 'checkpoint falhou' }
```

Se qualquer contagem real divergir de `6/7/10/80`, corrigir o texto para os valores observados somente depois de investigar a divergência; nunca publicar número esperado como evidência observada.

- [ ] **Passo 8: verificar PR final sem mudar Ready/Merge**

```powershell
$Pr = gh pr view $PrNumber --repo deraldinho/devex-homelab --json state,isDraft,headRefOid,baseRefName | ConvertFrom-Json
if ($Pr.state -ne 'OPEN' -or -not $Pr.isDraft -or $Pr.headRefOid -ne $FinalSha -or $Pr.baseRefName -ne 'atlas/issue-20-observation-runtime') { throw 'estado final da PR diverge do esperado' }
```

## Critérios de conclusão da A1

A1 só pode ser declarada concluída quando:

- os quatro contratos afetivos A1 existem em pt-BR;
- `config_afetiva.json` usa `versao_esquema=1` e os valores aprovados;
- timestamps são UTC;
- decaimento por meia-vida e limite offline de `3600 s` estão testados;
- impulsos permanecem limitados e não decidem foco;
- persistência atômica funciona e arquivo ausente/corrompido/temporalmente inválido retorna à personalidade-base com origem explícita;
- instalador inclui A1 sem ativar serviço;
- gate local integral está GREEN;
- Foundation CI está `success` no HEAD final exato;
- certificação física isolada está registrada se realmente executada;
- checkpoint está atualizado em pt-BR;
- nenhuma A2–A8, LLM, áudio, controle remoto ou mudança persistente de infraestrutura foi antecipada.
