"""Atlas Memory Preference Tracker — Tracker de preferências do operador.

Rastreia padrões de interação do operador para construir memória de
preferências: horários ativos, temas frequentes, estilo preferido.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PreferenceSignal:
    """Sinal de preferência derivado de uma interação."""
    category: str          # "schedule", "topic", "style", "approval", "rejection"
    key: str               # ex: "active_hour:14", "topic:l2jtoren", "style:direct"
    value: float = 1.0     # peso positivo (preferência) ou negativo (rejeição)
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.category or not self.key:
            raise ValueError("category e key nao podem ser vazios")
        if not self.timestamp:
            object.__setattr__(self, "timestamp", _utc_now())


@dataclass
class PreferenceProfile:
    """Perfil acumulado de preferências do operador."""
    schedule_hours: dict[int, float] = field(default_factory=dict)  # hora -> peso
    topics: dict[str, float] = field(default_factory=dict)          # topic -> peso
    styles: dict[str, float] = field(default_factory=dict)          # style -> peso
    approval_rate: float = 0.0
    total_interactions: int = 0
    last_updated: str = ""


class PreferenceTracker:
    """Rastreia preferências do operador com decaimento temporal.

    Persiste perfil em JSON para portabilidade e leveza no Pentium.
    """

    DECAY_FACTOR = 0.95        # decaimento por ciclo de manutenção
    MIN_WEIGHT = 0.01          # peso abaixo do qual a preferência é descartada
    MAX_ENTRIES_PER_CAT = 50   # limite de entradas por categoria

    def __init__(self, path: Path):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._profile = self._load()

    @property
    def profile(self) -> PreferenceProfile:
        return self._profile

    def record(self, signal: PreferenceSignal) -> None:
        """Registra um sinal de preferência."""
        self._profile.total_interactions += 1
        self._profile.last_updated = signal.timestamp or _utc_now()

        if signal.category == "schedule":
            try:
                hour = int(signal.key.split(":")[-1])
                current = self._profile.schedule_hours.get(hour, 0.0)
                self._profile.schedule_hours[hour] = current + signal.value
            except (ValueError, IndexError):
                pass

        elif signal.category == "topic":
            current = self._profile.topics.get(signal.key, 0.0)
            self._profile.topics[signal.key] = current + signal.value

        elif signal.category == "style":
            current = self._profile.styles.get(signal.key, 0.0)
            self._profile.styles[signal.key] = current + signal.value

        elif signal.category == "approval":
            total = self._profile.total_interactions
            rate = self._profile.approval_rate
            self._profile.approval_rate = (rate * (total - 1) + signal.value) / total

        self._save()

    def get_preference(self, category: str, key: str) -> float:
        """Obtém peso acumulado de uma preferência."""
        if category == "topic":
            return self._profile.topics.get(key, 0.0)
        elif category == "style":
            return self._profile.styles.get(key, 0.0)
        elif category == "schedule":
            try:
                hour = int(key.split(":")[-1])
                return self._profile.schedule_hours.get(hour, 0.0)
            except (ValueError, IndexError):
                return 0.0
        return 0.0

    def decay(self) -> None:
        """Aplica decaimento temporal a todas as preferências."""
        for hours_dict in [self._profile.schedule_hours]:
            to_remove = []
            for k, v in hours_dict.items():
                new_v = v * self.DECAY_FACTOR
                if new_v < self.MIN_WEIGHT:
                    to_remove.append(k)
                else:
                    hours_dict[k] = new_v
            for k in to_remove:
                del hours_dict[k]

        for str_dict in [self._profile.topics, self._profile.styles]:
            to_remove = []
            for k, v in str_dict.items():
                new_v = v * self.DECAY_FACTOR
                if new_v < self.MIN_WEIGHT:
                    to_remove.append(k)
                else:
                    str_dict[k] = new_v
            for k in to_remove:
                del str_dict[k]

        self._enforce_limits()
        self._save()

    def top_topics(self, n: int = 5) -> list[tuple[str, float]]:
        """Retorna os N tópicos mais relevantes."""
        sorted_topics = sorted(
            self._profile.topics.items(), key=lambda x: x[1], reverse=True
        )
        return sorted_topics[:n]

    def preferred_style(self) -> str | None:
        """Retorna o estilo preferido dominante, ou None."""
        if not self._profile.styles:
            return None
        return max(self._profile.styles, key=self._profile.styles.get)

    def active_hours(self) -> list[int]:
        """Retorna horas do dia com maior atividade (top 5)."""
        sorted_hours = sorted(
            self._profile.schedule_hours.items(), key=lambda x: x[1], reverse=True
        )
        return [h for h, _ in sorted_hours[:5]]

    def derive_signals_from_message(
        self,
        message: str,
        *,
        timestamp: str = "",
        topics: tuple[str, ...] = (),
    ) -> list[PreferenceSignal]:
        """Deriva sinais de preferência de uma mensagem do operador."""
        ts = timestamp or _utc_now()
        signals: list[PreferenceSignal] = []

        # Sinal de horário
        try:
            dt = datetime.fromisoformat(ts)
            hour = dt.hour
            signals.append(PreferenceSignal("schedule", f"active_hour:{hour}", 1.0, ts))
        except (ValueError, TypeError):
            pass

        # Sinais de tópico
        for topic in topics:
            signals.append(PreferenceSignal("topic", topic, 1.0, ts))

        # Detecção de estilo pela mensagem
        msg_lower = message.lower().strip()
        if len(msg_lower) < 30 or msg_lower.endswith("?"):
            signals.append(PreferenceSignal("style", "direct", 0.5, ts))
        elif any(kw in msg_lower for kw in ("como", "porque", "estratégia", "trade-off", "arquitetura")):
            signals.append(PreferenceSignal("style", "architect", 0.5, ts))
        elif any(kw in msg_lower for kw in ("ideia", "imagina", "criativo", "mundo", "lore")):
            signals.append(PreferenceSignal("style", "partner", 0.5, ts))
        else:
            signals.append(PreferenceSignal("style", "tool", 0.3, ts))

        return signals

    def _enforce_limits(self) -> None:
        """Mantém limites bounded por categoria."""
        for d in [self._profile.topics, self._profile.styles]:
            if len(d) > self.MAX_ENTRIES_PER_CAT:
                sorted_items = sorted(d.items(), key=lambda x: x[1], reverse=True)
                d.clear()
                d.update(sorted_items[:self.MAX_ENTRIES_PER_CAT])

    def _load(self) -> PreferenceProfile:
        if not self._path.exists():
            return PreferenceProfile()
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return PreferenceProfile(
                schedule_hours={int(k): v for k, v in data.get("schedule_hours", {}).items()},
                topics=dict(data.get("topics", {})),
                styles=dict(data.get("styles", {})),
                approval_rate=float(data.get("approval_rate", 0.0)),
                total_interactions=int(data.get("total_interactions", 0)),
                last_updated=str(data.get("last_updated", "")),
            )
        except (json.JSONDecodeError, TypeError, KeyError):
            return PreferenceProfile()

    def _save(self) -> None:
        data = {
            "schedule_hours": {str(k): v for k, v in self._profile.schedule_hours.items()},
            "topics": self._profile.topics,
            "styles": self._profile.styles,
            "approval_rate": self._profile.approval_rate,
            "total_interactions": self._profile.total_interactions,
            "last_updated": self._profile.last_updated,
        }
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._path)
