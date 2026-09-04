# Plano de Implementação — Atlas A1 Núcleo Afetivo

> **Para agentes de implementação:** SUB-SKILL OBRIGATÓRIA: usar `superpowers:subagent-driven-development` (recomendado) ou `superpowers:executing-plans` para executar este plano tarefa por tarefa. Os passos usam `- [ ]` para acompanhamento.

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
- Relógio de testes é explícito; nenhum teste usa `sleep()`.
- TDD obrigatório: RED observável antes de cada implementação de produção.
- Cada tarefa termina em commit pequeno e revisável.

## Estrutura de arquivos

### Criar

- `infrastructure/pentium/atlas/modelo_afetivo.py` — contratos, bounds e serialização.
- `infrastructure/pentium/atlas/configuracao_afetiva.py` — loader estrito do schema v1.
- `infrastructure/pentium/atlas/config_afetiva.json` — personalidade-base e política de decaimento.
- `infrastructure/pentium/atlas/motor_afetivo.py` — criação, impulso, decaimento e atenuação offline.
- `infrastructure/pentium/atlas/persistencia_afetiva.py` — snapshot atômico e restauração segura.
- `infrastructure/pentium/atlas/tests/test_modelo_afetivo.py`.
- `infrastructure/pentium/atlas/tests/test_configuracao_afetiva.py`.
- `infrastructure/pentium/atlas/tests/test_motor_afetivo.py`.
- `infrastructure/pentium/atlas/tests/test_persistencia_afetiva.py`.
- `infrastructure/pentium/atlas/tests/test_nucleo_afetivo_empacotamento.py`.

### Modificar

- `infrastructure/pentium/atlas/install-user.sh` — incluir A1 sem ativar serviço.
- `.github/workflows/foundation-ci.yml` — compilar/validar A1 e emitir marker.
- `docs/as-built/2026-09-02-baseline.md` — registrar apenas evidência observada no HEAD final.

---

## Tarefa 1 — Contratos e invariantes do modelo afetivo

**Arquivos:**
- Criar: `infrastructure/pentium/atlas/modelo_afetivo.py`
- Criar: `infrastructure/pentium/atlas/tests/test_modelo_afetivo.py`

**Interfaces produzidas:**

```python
EstadoConsciencia(str, Enum)
PersonalidadeBase(valencia, ativacao, estresse, confianca, engajamento, curiosidade)
PoliticaDecaimento(
    meia_vida_valencia_s,
    meia_vida_ativacao_s,
    meia_vida_estresse_s,
    meia_vida_confianca_s,
    meia_vida_engajamento_s,
    meia_vida_curiosidade_s,
    limite_atenuacao_offline_s,
)
EstadoAfetivo(
    valencia,
    ativacao,
    estresse,
    confianca,
    engajamento,
    curiosidade,
    foco_atencao,
    estado_consciencia,
    atualizado_em,
)
ImpulsoAfetivo(
    tipo,
    motivo,
    delta_valencia,
    delta_ativacao,
    delta_estresse,
    delta_confianca,
    delta_engajamento,
    delta_curiosidade,
)
```

- [ ] **Passo 1: escrever o teste RED**

Criar `test_modelo_afetivo.py`:

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
        personalidade = PersonalidadeBase(2, -1, 2, -1, 2, -1)
        estado = EstadoAfetivo(
            -2, 2, -1, 2, -1, 2,
            None,
            EstadoConsciencia.RETOMANDO,
            "2026-09-04T15:00:00+00:00",
        )
        self.assertEqual(personalidade.valencia, 1.0)
        self.assertEqual(personalidade.ativacao, 0.0)
        self.assertEqual(estado.valencia, -1.0)
        self.assertEqual(estado.ativacao, 1.0)
        self.assertEqual(estado.estresse, 0.0)
        self.assertEqual(estado.confianca, 1.0)

    def test_impulso_limita_deltas(self):
        impulso = ImpulsoAfetivo("teste", "teste", -4, 4, -4, 4, -4, 4)
        self.assertEqual(impulso.delta_valencia, -1.0)
        self.assertEqual(impulso.delta_ativacao, 1.0)
        self.assertEqual(impulso.delta_estresse, -1.0)
        self.assertEqual(impulso.delta_confianca, 1.0)

    def test_politica_rejeita_meia_vida_invalida(self):
        with self.assertRaises(ValueError):
            PoliticaDecaimento(0, 1200, 1800, 14400, 7200, 10800, 1800)

    def test_timestamp_precisa_ser_aware(self):
        with self.assertRaises(ValueError):
            EstadoAfetivo(
                0.2, 0.25, 0.1, 0.7, 0.5, 0.75,
                None, EstadoConsciencia.RETOMANDO,
                "2026-09-04T15:00:00",
            )

    def test_contratos_sao_frozen_e_json_serializaveis(self):
        estado = EstadoAfetivo(
            0.2, 0.25, 0.1, 0.7, 0.5, 0.75,
            None, EstadoConsciencia.RETOMANDO,
            "2026-09-04T15:00:00+00:00",
        )
        with self.assertRaises(dataclasses.FrozenInstanceError):
            estado.estresse = 0.8
        encoded = json.dumps(estado.to_dict(), ensure_ascii=False, sort_keys=True)
        self.assertIn('"estado_consciencia": "retomando"', encoded)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Passo 2: executar e observar RED**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_modelo_afetivo -v
```

Esperado: FAIL por `ModuleNotFoundError` para `modelo_afetivo`.

- [ ] **Passo 3: implementar `modelo_afetivo.py` exatamente com estes invariantes**

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


def _limitar_01(valor: float) -> float:
    return max(0.0, min(1.0, float(valor)))


def _limitar_valencia(valor: float) -> float:
    return max(-1.0, min(1.0, float(valor)))


def _limitar_delta(valor: float) -> float:
    return max(-1.0, min(1.0, float(valor)))


def _validar_timestamp_aware(valor: str) -> str:
    try:
        parsed = datetime.fromisoformat(valor)
    except (TypeError, ValueError) as exc:
        raise ValueError("timestamp afetivo deve ser ISO-8601 válido") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp afetivo deve possuir timezone")
    return valor


class EstadoConsciencia(str, Enum):
    ATIVO = "ativo"
    DEGRADADO = "degradado"
    ISOLADO = "isolado"
    RETOMANDO = "retomando"


@dataclass(frozen=True)
class PersonalidadeBase:
    valencia: float
    ativacao: float
    estresse: float
    confianca: float
    engajamento: float
    curiosidade: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "valencia", _limitar_valencia(self.valencia))
        for nome in ("ativacao", "estresse", "confianca", "engajamento", "curiosidade"):
            object.__setattr__(self, nome, _limitar_01(getattr(self, nome)))


@dataclass(frozen=True)
class PoliticaDecaimento:
    meia_vida_valencia_s: float
    meia_vida_ativacao_s: float
    meia_vida_estresse_s: float
    meia_vida_confianca_s: float
    meia_vida_engajamento_s: float
    meia_vida_curiosidade_s: float
    limite_atenuacao_offline_s: float

    def __post_init__(self) -> None:
        for nome in (
            "meia_vida_valencia_s",
            "meia_vida_ativacao_s",
            "meia_vida_estresse_s",
            "meia_vida_confianca_s",
            "meia_vida_engajamento_s",
            "meia_vida_curiosidade_s",
        ):
            valor = float(getattr(self, nome))
            if valor <= 0:
                raise ValueError(f"{nome} deve ser > 0")
            object.__setattr__(self, nome, valor)
        limite = float(self.limite_atenuacao_offline_s)
        if limite < 0:
            raise ValueError("limite_atenuacao_offline_s deve ser >= 0")
        object.__setattr__(self, "limite_atenuacao_offline_s", limite)


@dataclass(frozen=True)
class EstadoAfetivo:
    valencia: float
    ativacao: float
    estresse: float
    confianca: float
    engajamento: float
    curiosidade: float
    foco_atencao: str | None
    estado_consciencia: EstadoConsciencia
    atualizado_em: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "valencia", _limitar_valencia(self.valencia))
        for nome in ("ativacao", "estresse", "confianca", "engajamento", "curiosidade"):
            object.__setattr__(self, nome, _limitar_01(getattr(self, nome)))
        if self.foco_atencao is not None and not self.foco_atencao.strip():
            raise ValueError("foco_atencao não pode ser vazio")
        object.__setattr__(self, "atualizado_em", _validar_timestamp_aware(self.atualizado_em))

    def to_dict(self) -> dict[str, Any]:
        return {
            "valencia": self.valencia,
            "ativacao": self.ativacao,
            "estresse": self.estresse,
            "confianca": self.confianca,
            "engajamento": self.engajamento,
            "curiosidade": self.curiosidade,
            "foco_atencao": self.foco_atencao,
            "estado_consciencia": self.estado_consciencia.value,
            "atualizado_em": self.atualizado_em,
        }


@dataclass(frozen=True)
class ImpulsoAfetivo:
    tipo: str
    motivo: str
    delta_valencia: float
    delta_ativacao: float
    delta_estresse: float
    delta_confianca: float
    delta_engajamento: float
    delta_curiosidade: float

    def __post_init__(self) -> None:
        if not self.tipo.strip():
            raise ValueError("tipo do impulso não pode ser vazio")
        for nome in (
            "delta_valencia",
            "delta_ativacao",
            "delta_estresse",
            "delta_confianca",
            "delta_engajamento",
            "delta_curiosidade",
        ):
            object.__setattr__(self, nome, _limitar_delta(getattr(self, nome)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "tipo": self.tipo,
            "motivo": self.motivo,
            "delta_valencia": self.delta_valencia,
            "delta_ativacao": self.delta_ativacao,
            "delta_estresse": self.delta_estresse,
            "delta_confianca": self.delta_confianca,
            "delta_engajamento": self.delta_engajamento,
            "delta_curiosidade": self.delta_curiosidade,
        }
```

- [ ] **Passo 4: executar teste do modelo e regressão Atlas**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_modelo_afetivo -v
python3 -m unittest discover -s infrastructure/pentium/atlas/tests -p 'test_*.py' -v
```

Esperado: novo teste GREEN e os 60 testes Atlas anteriores continuam GREEN.

- [ ] **Passo 5: commit**

```bash
git add infrastructure/pentium/atlas/modelo_afetivo.py infrastructure/pentium/atlas/tests/test_modelo_afetivo.py
git commit -m "feat(atlas): adicionar contratos do estado afetivo"
```

---

## Tarefa 2 — Configuração da personalidade-base e decaimento

**Arquivos:**
- Criar: `infrastructure/pentium/atlas/configuracao_afetiva.py`
- Criar: `infrastructure/pentium/atlas/config_afetiva.json`
- Criar: `infrastructure/pentium/atlas/tests/test_configuracao_afetiva.py`

**Interface produzida:**

```python
carregar_configuracao_afetiva(path: Path) -> tuple[PersonalidadeBase, PoliticaDecaimento]
```

**Valores iniciais propostos por este plano, ainda calibráveis antes da execução:**

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

Esses valores materializam somente as tendências aprovadas: valência levemente positiva, ativação baixa, estresse baixo, confiança alta, engajamento moderado, curiosidade alta; ativação/estresse recuperam mais rápido, valência em ritmo intermediário, demais dimensões mais lentamente.

- [ ] **Passo 1: escrever teste RED do loader**

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

    def test_rejeita_campo_obrigatorio_ausente(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "config.json"
            path.write_text(
                json.dumps({"versao_schema": 1, "personalidade_base": {}, "decaimento": {}}),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                carregar_configuracao_afetiva(path)

    def test_rejeita_meia_vida_invalida(self):
        payload = json.loads(CONFIG.read_text(encoding="utf-8"))
        payload["decaimento"]["meia_vida_segundos"]["estresse"] = 0
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "config.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                carregar_configuracao_afetiva(path)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Passo 2: executar e observar RED**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_configuracao_afetiva -v
```

Esperado: FAIL por módulo/configuração ausente.

- [ ] **Passo 3: criar `config_afetiva.json` com o JSON exato acima**

Validar:

```bash
python3 -m json.tool infrastructure/pentium/atlas/config_afetiva.json >/dev/null
```

Esperado: exit 0.

- [ ] **Passo 4: implementar `configuracao_afetiva.py`**

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .modelo_afetivo import PersonalidadeBase, PoliticaDecaimento


def _objeto(payload: dict[str, Any], chave: str) -> dict[str, Any]:
    valor = payload.get(chave)
    if not isinstance(valor, dict):
        raise ValueError(f"{chave} deve ser objeto")
    return valor


def _obrigatorio(payload: dict[str, Any], chave: str) -> Any:
    if chave not in payload:
        raise ValueError(f"campo obrigatório ausente: {chave}")
    return payload[chave]


def carregar_configuracao_afetiva(
    path: Path,
) -> tuple[PersonalidadeBase, PoliticaDecaimento]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("configuração afetiva inválida") from exc
    if not isinstance(payload, dict):
        raise ValueError("configuração afetiva deve ser objeto")
    if payload.get("versao_schema") != 1:
        raise ValueError("configuração afetiva versao_schema deve ser 1")

    base = _objeto(payload, "personalidade_base")
    decaimento = _objeto(payload, "decaimento")
    meias = _objeto(decaimento, "meia_vida_segundos")

    personalidade = PersonalidadeBase(
        _obrigatorio(base, "valencia"),
        _obrigatorio(base, "ativacao"),
        _obrigatorio(base, "estresse"),
        _obrigatorio(base, "confianca"),
        _obrigatorio(base, "engajamento"),
        _obrigatorio(base, "curiosidade"),
    )
    politica = PoliticaDecaimento(
        _obrigatorio(meias, "valencia"),
        _obrigatorio(meias, "ativacao"),
        _obrigatorio(meias, "estresse"),
        _obrigatorio(meias, "confianca"),
        _obrigatorio(meias, "engajamento"),
        _obrigatorio(meias, "curiosidade"),
        _obrigatorio(decaimento, "limite_atenuacao_offline_segundos"),
    )
    return personalidade, politica
```

- [ ] **Passo 5: executar testes e regressão**

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

## Tarefa 3 — Motor puro de impulso e decaimento

**Arquivos:**
- Criar: `infrastructure/pentium/atlas/motor_afetivo.py`
- Criar: `infrastructure/pentium/atlas/tests/test_motor_afetivo.py`

**Interfaces produzidas:**

```python
criar_estado_inicial(personalidade, atualizado_em) -> EstadoAfetivo
aplicar_impulso(estado, impulso, atualizado_em) -> EstadoAfetivo
decair_estado(estado, personalidade, politica, atualizado_em) -> EstadoAfetivo
atenuar_estado_offline(estado, personalidade, politica, retomado_em) -> EstadoAfetivo
```

**Fórmula:**

```text
novo = base + (atual - base) * 0.5 ** (segundos / meia_vida)
```

- [ ] **Passo 1: escrever teste RED**

Criar `test_motor_afetivo.py`:

```python
import unittest

from infrastructure.pentium.atlas.modelo_afetivo import (
    EstadoAfetivo,
    EstadoConsciencia,
    ImpulsoAfetivo,
    PersonalidadeBase,
    PoliticaDecaimento,
)
from infrastructure.pentium.atlas.motor_afetivo import (
    aplicar_impulso,
    atenuar_estado_offline,
    criar_estado_inicial,
    decair_estado,
)


class MotorAfetivoTests(unittest.TestCase):
    def setUp(self):
        self.personalidade = PersonalidadeBase(0.2, 0.25, 0.1, 0.7, 0.5, 0.75)
        self.politica = PoliticaDecaimento(3600, 1200, 1800, 14400, 7200, 10800, 1800)

    def test_estado_inicial_nasce_no_baseline_e_retomando(self):
        estado = criar_estado_inicial(self.personalidade, "2026-09-04T15:00:00+00:00")
        self.assertEqual(estado.valencia, 0.2)
        self.assertEqual(estado.estresse, 0.1)
        self.assertEqual(estado.estado_consciencia, EstadoConsciencia.RETOMANDO)

    def test_impulso_soma_limita_e_preserva_foco(self):
        estado = EstadoAfetivo(
            0.2, 0.25, 0.1, 0.7, 0.5, 0.75,
            "x99", EstadoConsciencia.ATIVO,
            "2026-09-04T15:00:00+00:00",
        )
        impulso = ImpulsoAfetivo("perda", "teste", -0.8, 0.9, 1.0, -0.8, 0.4, 0.1)
        novo = aplicar_impulso(estado, impulso, "2026-09-04T15:00:01+00:00")
        self.assertAlmostEqual(novo.valencia, -0.6)
        self.assertEqual(novo.ativacao, 1.0)
        self.assertEqual(novo.estresse, 1.0)
        self.assertEqual(novo.foco_atencao, "x99")
        self.assertEqual(novo.estado_consciencia, EstadoConsciencia.ATIVO)

    def test_decaimento_respeita_meia_vida(self):
        estado = EstadoAfetivo(
            1.0, 0.25, 0.9, 0.7, 0.5, 0.75,
            None, EstadoConsciencia.ATIVO,
            "2026-09-04T15:00:00+00:00",
        )
        novo = decair_estado(
            estado,
            self.personalidade,
            self.politica,
            "2026-09-04T16:00:00+00:00",
        )
        self.assertAlmostEqual(novo.valencia, 0.6, places=6)

    def test_rejeita_tempo_regressivo(self):
        estado = criar_estado_inicial(self.personalidade, "2026-09-04T15:00:00+00:00")
        with self.assertRaises(ValueError):
            decair_estado(
                estado,
                self.personalidade,
                self.politica,
                "2026-09-04T14:59:59+00:00",
            )

    def test_atenuacao_offline_limita_tempo_e_entra_retomando(self):
        estado = EstadoAfetivo(
            0.2, 0.25, 0.9, 0.7, 0.5, 0.75,
            "x99", EstadoConsciencia.DEGRADADO,
            "2026-09-04T00:00:00+00:00",
        )
        novo = atenuar_estado_offline(
            estado,
            self.personalidade,
            self.politica,
            "2026-09-04T12:00:00+00:00",
        )
        self.assertAlmostEqual(novo.estresse, 0.5, places=6)
        self.assertEqual(novo.estado_consciencia, EstadoConsciencia.RETOMANDO)
        self.assertEqual(novo.foco_atencao, "x99")
        self.assertEqual(novo.atualizado_em, "2026-09-04T12:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Passo 2: executar e observar RED**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_motor_afetivo -v
```

Esperado: FAIL por `motor_afetivo` ausente.

- [ ] **Passo 3: implementar `motor_afetivo.py`**

```python
from __future__ import annotations

from datetime import datetime

from .modelo_afetivo import (
    EstadoAfetivo,
    EstadoConsciencia,
    ImpulsoAfetivo,
    PersonalidadeBase,
    PoliticaDecaimento,
)


def _parse_timestamp(valor: str) -> datetime:
    parsed = datetime.fromisoformat(valor)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp afetivo deve possuir timezone")
    return parsed


def _segundos_entre(inicio: str, fim: str) -> float:
    segundos = (_parse_timestamp(fim) - _parse_timestamp(inicio)).total_seconds()
    if segundos < 0:
        raise ValueError("tempo afetivo não pode regredir")
    return segundos


def _decair(valor: float, base: float, segundos: float, meia_vida: float) -> float:
    return base + (valor - base) * (0.5 ** (segundos / meia_vida))


def criar_estado_inicial(
    personalidade: PersonalidadeBase,
    atualizado_em: str,
) -> EstadoAfetivo:
    return EstadoAfetivo(
        personalidade.valencia,
        personalidade.ativacao,
        personalidade.estresse,
        personalidade.confianca,
        personalidade.engajamento,
        personalidade.curiosidade,
        None,
        EstadoConsciencia.RETOMANDO,
        atualizado_em,
    )


def aplicar_impulso(
    estado: EstadoAfetivo,
    impulso: ImpulsoAfetivo,
    atualizado_em: str,
) -> EstadoAfetivo:
    _segundos_entre(estado.atualizado_em, atualizado_em)
    return EstadoAfetivo(
        estado.valencia + impulso.delta_valencia,
        estado.ativacao + impulso.delta_ativacao,
        estado.estresse + impulso.delta_estresse,
        estado.confianca + impulso.delta_confianca,
        estado.engajamento + impulso.delta_engajamento,
        estado.curiosidade + impulso.delta_curiosidade,
        estado.foco_atencao,
        estado.estado_consciencia,
        atualizado_em,
    )


def _valores_decaidos(
    estado: EstadoAfetivo,
    personalidade: PersonalidadeBase,
    politica: PoliticaDecaimento,
    segundos: float,
) -> tuple[float, float, float, float, float, float]:
    return (
        _decair(estado.valencia, personalidade.valencia, segundos, politica.meia_vida_valencia_s),
        _decair(estado.ativacao, personalidade.ativacao, segundos, politica.meia_vida_ativacao_s),
        _decair(estado.estresse, personalidade.estresse, segundos, politica.meia_vida_estresse_s),
        _decair(estado.confianca, personalidade.confianca, segundos, politica.meia_vida_confianca_s),
        _decair(estado.engajamento, personalidade.engajamento, segundos, politica.meia_vida_engajamento_s),
        _decair(estado.curiosidade, personalidade.curiosidade, segundos, politica.meia_vida_curiosidade_s),
    )


def decair_estado(
    estado: EstadoAfetivo,
    personalidade: PersonalidadeBase,
    politica: PoliticaDecaimento,
    atualizado_em: str,
) -> EstadoAfetivo:
    segundos = _segundos_entre(estado.atualizado_em, atualizado_em)
    valores = _valores_decaidos(estado, personalidade, politica, segundos)
    return EstadoAfetivo(
        *valores,
        estado.foco_atencao,
        estado.estado_consciencia,
        atualizado_em,
    )


def atenuar_estado_offline(
    estado: EstadoAfetivo,
    personalidade: PersonalidadeBase,
    politica: PoliticaDecaimento,
    retomado_em: str,
) -> EstadoAfetivo:
    total = _segundos_entre(estado.atualizado_em, retomado_em)
    efetivo = min(total, politica.limite_atenuacao_offline_s)
    valores = _valores_decaidos(estado, personalidade, politica, efetivo)
    return EstadoAfetivo(
        *valores,
        estado.foco_atencao,
        EstadoConsciencia.RETOMANDO,
        retomado_em,
    )
```

- [ ] **Passo 4: executar teste do motor e regressão Atlas**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_motor_afetivo -v
python3 -m unittest discover -s infrastructure/pentium/atlas/tests -p 'test_*.py' -v
```

Esperado: GREEN.

- [ ] **Passo 5: commit**

```bash
git add infrastructure/pentium/atlas/motor_afetivo.py infrastructure/pentium/atlas/tests/test_motor_afetivo.py
git commit -m "feat(atlas): implementar motor afetivo determinístico"
```

---

## Tarefa 4 — Persistência atômica e restauração segura

**Arquivos:**
- Criar: `infrastructure/pentium/atlas/persistencia_afetiva.py`
- Criar: `infrastructure/pentium/atlas/tests/test_persistencia_afetiva.py`

**Interfaces produzidas:**

```python
VERSAO_SNAPSHOT_AFETIVO = 1
PersistenciaAfetivaError(RuntimeError)
ResultadoRestauracao(estado: EstadoAfetivo, origem: str, erro: str | None)
salvar_estado_afetivo(path, estado) -> None
carregar_estado_afetivo(path) -> EstadoAfetivo
restaurar_estado_afetivo(path, personalidade, politica, retomado_em) -> ResultadoRestauracao
```

- [ ] **Passo 1: escrever teste RED**

Criar `test_persistencia_afetiva.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.modelo_afetivo import (
    EstadoAfetivo,
    EstadoConsciencia,
    PersonalidadeBase,
    PoliticaDecaimento,
)
from infrastructure.pentium.atlas.motor_afetivo import criar_estado_inicial
from infrastructure.pentium.atlas.persistencia_afetiva import (
    carregar_estado_afetivo,
    restaurar_estado_afetivo,
    salvar_estado_afetivo,
)


class PersistenciaAfetivaTests(unittest.TestCase):
    def setUp(self):
        self.personalidade = PersonalidadeBase(0.2, 0.25, 0.1, 0.7, 0.5, 0.75)
        self.politica = PoliticaDecaimento(3600, 1200, 1800, 14400, 7200, 10800, 1800)

    def test_round_trip_atomico_nao_deixa_temporario(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "estado-afetivo.json"
            estado = criar_estado_inicial(self.personalidade, "2026-09-04T15:00:00+00:00")
            salvar_estado_afetivo(path, estado)
            self.assertEqual(carregar_estado_afetivo(path), estado)
            self.assertFalse((Path(temp) / "estado-afetivo.json.tmp").exists())
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["versao"], 1)

    def test_snapshot_ausente_retorna_baseline_retomando(self):
        with tempfile.TemporaryDirectory() as temp:
            resultado = restaurar_estado_afetivo(
                Path(temp) / "ausente.json",
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
                path,
                self.personalidade,
                self.politica,
                "2026-09-04T15:00:00+00:00",
            )
            self.assertEqual(resultado.origem, "baseline")
            self.assertEqual(resultado.erro, "snapshot_invalido")

    def test_snapshot_valido_aplica_atenuacao_offline_limitada(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "estado.json"
            estado = EstadoAfetivo(
                0.2, 0.25, 0.9, 0.7, 0.5, 0.75,
                "x99", EstadoConsciencia.DEGRADADO,
                "2026-09-04T00:00:00+00:00",
            )
            salvar_estado_afetivo(path, estado)
            resultado = restaurar_estado_afetivo(
                path,
                self.personalidade,
                self.politica,
                "2026-09-04T12:00:00+00:00",
            )
            self.assertEqual(resultado.origem, "snapshot")
            self.assertIsNone(resultado.erro)
            self.assertAlmostEqual(resultado.estado.estresse, 0.5, places=6)
            self.assertEqual(resultado.estado.estado_consciencia, EstadoConsciencia.RETOMANDO)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Passo 2: executar e observar RED**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_persistencia_afetiva -v
```

Esperado: FAIL por `persistencia_afetiva` ausente.

- [ ] **Passo 3: implementar `persistencia_afetiva.py`**

```python
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from .modelo_afetivo import (
    EstadoAfetivo,
    EstadoConsciencia,
    PersonalidadeBase,
    PoliticaDecaimento,
)
from .motor_afetivo import atenuar_estado_offline, criar_estado_inicial

VERSAO_SNAPSHOT_AFETIVO = 1


class PersistenciaAfetivaError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResultadoRestauracao:
    estado: EstadoAfetivo
    origem: str
    erro: str | None = None


def salvar_estado_afetivo(path: Path, estado: EstadoAfetivo) -> None:
    payload = {"versao": VERSAO_SNAPSHOT_AFETIVO, "estado": estado.to_dict()}
    temporario = path.with_name(path.name + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with temporario.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporario, path)
    except OSError as exc:
        try:
            temporario.unlink(missing_ok=True)
        except OSError:
            pass
        raise PersistenciaAfetivaError(str(exc)) from exc


def carregar_estado_afetivo(path: Path) -> EstadoAfetivo:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise PersistenciaAfetivaError(str(exc)) from exc
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict) or payload.get("versao") != VERSAO_SNAPSHOT_AFETIVO:
            raise ValueError("versão de snapshot inválida")
        estado = payload["estado"]
        if not isinstance(estado, dict):
            raise ValueError("estado deve ser objeto")
        return EstadoAfetivo(
            estado["valencia"],
            estado["ativacao"],
            estado["estresse"],
            estado["confianca"],
            estado["engajamento"],
            estado["curiosidade"],
            estado.get("foco_atencao"),
            EstadoConsciencia(estado["estado_consciencia"]),
            estado["atualizado_em"],
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise PersistenciaAfetivaError("snapshot afetivo inválido") from exc


def restaurar_estado_afetivo(
    path: Path,
    personalidade: PersonalidadeBase,
    politica: PoliticaDecaimento,
    retomado_em: str,
) -> ResultadoRestauracao:
    try:
        estado = carregar_estado_afetivo(path)
    except FileNotFoundError:
        return ResultadoRestauracao(
            criar_estado_inicial(personalidade, retomado_em),
            "baseline",
            "snapshot_ausente",
        )
    except PersistenciaAfetivaError:
        return ResultadoRestauracao(
            criar_estado_inicial(personalidade, retomado_em),
            "baseline",
            "snapshot_invalido",
        )
    return ResultadoRestauracao(
        atenuar_estado_offline(estado, personalidade, politica, retomado_em),
        "snapshot",
        None,
    )
```

- [ ] **Passo 4: executar testes e regressão Atlas**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_persistencia_afetiva -v
python3 -m unittest discover -s infrastructure/pentium/atlas/tests -p 'test_*.py' -v
```

Esperado: GREEN.

- [ ] **Passo 5: commit**

```bash
git add infrastructure/pentium/atlas/persistencia_afetiva.py infrastructure/pentium/atlas/tests/test_persistencia_afetiva.py
git commit -m "feat(atlas): persistir e restaurar estado afetivo"
```

---

## Tarefa 5 — Empacotamento e gate de CI

**Arquivos:**
- Criar: `infrastructure/pentium/atlas/tests/test_nucleo_afetivo_empacotamento.py`
- Modificar: `infrastructure/pentium/atlas/install-user.sh`
- Modificar: `.github/workflows/foundation-ci.yml`

**Markers produzidos:**

```text
ATLAS_NUCLEO_AFETIVO_INSTALL_PASS
DEVEX_HOMELAB_ATLAS_NUCLEO_AFETIVO_PASS
```

- [ ] **Passo 1: escrever teste RED do empacotamento**

```python
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ATLAS = ROOT / "infrastructure" / "pentium" / "atlas"
WORKFLOW = ROOT / ".github" / "workflows" / "foundation-ci.yml"


class NucleoAfetivoEmpacotamentoTests(unittest.TestCase):
    def test_installer_inclui_a1_sem_ativar_servico(self):
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
        for nome in (
            "modelo_afetivo.py",
            "configuracao_afetiva.py",
            "motor_afetivo.py",
            "persistencia_afetiva.py",
            "config_afetiva.json",
        ):
            self.assertIn(nome, text)
        self.assertIn("DEVEX_HOMELAB_ATLAS_NUCLEO_AFETIVO_PASS", text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Passo 2: executar e observar RED**

```bash
python3 -m unittest infrastructure.pentium.atlas.tests.test_nucleo_afetivo_empacotamento -v
```

Esperado: FAIL porque installer/CI ainda não incluem A1.

- [ ] **Passo 3: modificar `install-user.sh`**

No primeiro loop `for file in`, inserir antes de `cli.py`:

```text
  modelo_afetivo.py \
  configuracao_afetiva.py \
  motor_afetivo.py \
  persistencia_afetiva.py \
```

Trocar:

```bash
for config in config.json observation_config.json; do
```

por:

```bash
for config in config.json observation_config.json config_afetiva.json; do
```

Adicionar os quatro módulos ao bloco `python3 -m py_compile` e, após validação de `observation_config.json`, adicionar:

```bash
python3 -m json.tool "${TARGET_DIR}/config_afetiva.json" >/dev/null
```

Antes da linha `run=...`, adicionar:

```bash
echo "ATLAS_NUCLEO_AFETIVO_INSTALL_PASS"
```

- [ ] **Passo 4: modificar `.github/workflows/foundation-ci.yml`**

No gate Atlas, acrescentar ao `py_compile`:

```text
"$atlas/modelo_afetivo.py"
"$atlas/configuracao_afetiva.py"
"$atlas/motor_afetivo.py"
"$atlas/persistencia_afetiva.py"
```

Após `observation_config.json`, adicionar:

```bash
python3 -m json.tool "$atlas/config_afetiva.json" >/dev/null
```

Após `DEVEX_HOMELAB_ATLAS_OBSERVATION_PASS`, adicionar:

```bash
echo 'DEVEX_HOMELAB_ATLAS_NUCLEO_AFETIVO_PASS'
```

- [ ] **Passo 5: executar gates locais**

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

- [ ] **Passo 6: executar regressão completa usada no baseline**

```bash
python3 -m unittest discover -s infrastructure/network/tests -p 'test_*.py' -v
python3 -m unittest discover -s infrastructure/pentium/heartbeat/tests -p 'test_*.py' -v
python3 -m unittest discover -s infrastructure/pentium/agent/tests -p 'test_*.py' -v
python3 -m unittest discover -s infrastructure/pentium/atlas/tests -p 'test_*.py' -v
git diff --check
```

Esperado: Network 6, Heartbeat 7, Pentium Agent 10 e todos os testes Atlas legados + A1 GREEN; `git diff --check` sem saída.

- [ ] **Passo 7: commit**

```bash
git add .github/workflows/foundation-ci.yml infrastructure/pentium/atlas/install-user.sh infrastructure/pentium/atlas/tests/test_nucleo_afetivo_empacotamento.py
git commit -m "ci(atlas): certificar núcleo afetivo A1"
```

---

## Tarefa 6 — Gate final, as-built e PR Draft

**Arquivo:**
- Modificar: `docs/as-built/2026-09-02-baseline.md`

- [ ] **Passo 1: verificar isolamento de escopo**

```bash
git diff 1a28a54a051d152d83cf919a7f570e1bacccdf2e...HEAD -- infrastructure/pentium/atlas
grep -RniE 'grpc|https|socket|named pipe|traceroute|ssh|llm|tts|stt' \
  infrastructure/pentium/atlas/modelo_afetivo.py \
  infrastructure/pentium/atlas/configuracao_afetiva.py \
  infrastructure/pentium/atlas/motor_afetivo.py \
  infrastructure/pentium/atlas/persistencia_afetiva.py || true
```

Esperado: nenhuma implementação de transporte, diagnóstico ativo ou LLM em A1.

- [ ] **Passo 2: executar gate do HEAD de código**

```bash
echo "HEAD_CODIGO=$(git rev-parse HEAD)"
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

Registrar SHA e contagens exibidas pelos comandos. Resultado de SHA anterior não vale.

- [ ] **Passo 3: registrar as-built factual**

Adicionar ao final de `docs/as-built/2026-09-02-baseline.md` uma seção `## Atlas A1 — Núcleo Afetivo — 2026-09-04` contendo somente:

```text
- SHA exato certificado localmente;
- contagens reais Network/Heartbeat/Pentium Agent/Atlas;
- módulos A1 implementados;
- validações JSON/bash/diff realizadas;
- zero chamada de LLM;
- zero alteração de rede/SSH/Tailscale/firewall/modem;
- nenhum serviço persistente A1 instalado/ativado;
- certificação física/soak: não executada, se continuar não executada.
```

- [ ] **Passo 4: commit documental e novo gate no novo HEAD**

```bash
git add docs/as-built/2026-09-02-baseline.md
git commit -m "docs(atlas): registrar implementação A1 do núcleo afetivo"
echo "HEAD_FINAL=$(git rev-parse HEAD)"
python3 -m unittest discover -s infrastructure/network/tests -p 'test_*.py' -v
python3 -m unittest discover -s infrastructure/pentium/heartbeat/tests -p 'test_*.py' -v
python3 -m unittest discover -s infrastructure/pentium/agent/tests -p 'test_*.py' -v
python3 -m unittest discover -s infrastructure/pentium/atlas/tests -p 'test_*.py' -v
git diff --check
```

Esperado: GREEN no novo HEAD final.

- [ ] **Passo 5: push e PR Draft**

Fazer push de `atlas/issue-20-motor-estado-afetivo` e criar PR Draft com:

```text
base: atlas/issue-20-observation-runtime
head: atlas/issue-20-motor-estado-afetivo
título: feat(atlas): adicionar A1 núcleo afetivo determinístico
```

Não marcar Ready e não mergear.

- [ ] **Passo 6: verificar Foundation CI no HEAD final**

Aguardar o workflow e aceitar o gate somente se `completed/success` corresponder exatamente ao `HEAD_FINAL` obtido no Passo 4.

- [ ] **Passo 7: publicar `/checkpoint` pt-BR**

O comentário deve conter:

```text
/checkpoint — Atlas A1 Núcleo Afetivo
- HEAD exato final
- contratos e módulos implementados
- evidência RED→GREEN por tarefa
- contagens locais reais
- Foundation CI do mesmo SHA
- limites: sem LLM, sem rede nova, sem serviço persistente, sem certificação física se não realizada
- blockers/gates ainda existentes
- próximo passo seguro: A2 — Entidades, vínculos e expectativas
```

---

## Auto-revisão do plano

### Cobertura

A1 cobre exatamente: `EstadoAfetivo`, `PersonalidadeBase`, `ImpulsoAfetivo`, `EstadoConsciencia` necessário à retomada, bounds, decaimento temporal por dimensão, atenuação offline limitada, persistência atômica e fallback seguro.

A1 não implementa responsabilidades das próximas slices: vínculo/entidades/expectativas (A2), percepção/correlação (A3), seleção de foco e emoções derivadas (A4), Agente de Nó C++ (A5), transportes (A6), diagnóstico ativo (A7) e integração/certificação ampla (A8).

### Consistência

- `EstadoAfetivo.atualizado_em` é ISO-8601 aware.
- `foco_atencao` é persistido, mas A1 não decide qual foco vence.
- `EstadoConsciencia` existe para bootstrap/restauração; transições operacionais completas não entram em A1.
- Decaimento nunca consulta relógio oculto.
- Snapshot A1 schema v1 não antecipa incidentes/expectativas ainda inexistentes; evolução futura exige migração explícita.
- Estado técnico não é importado nem modificado pelo Motor Afetivo.

### Decisões numéricas novas deste plano

Os seis valores da personalidade-base e as meias-vidas são propostas concretas necessárias para tornar a A1 executável. Elas não foram aprovadas numericamente durante o design; a execução do plano só deve começar depois de o usuário aceitar esses números ou solicitar ajuste.

### Verificação de placeholders

Não há `TBD`, `TODO`, função sem assinatura, teste sem comportamento esperado nem passo de implementação dependente de código não definido neste plano.