"""Atlas Hypothesis Engine — Motor de hipóteses técnicas.

Permite ao Atlas formular, investigar e documentar hipóteses
de diagnóstico técnico baseadas em observações e tendências.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Mapping


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class HypothesisStatus(str, Enum):
    PROPOSED = "proposed"
    INVESTIGATING = "investigating"
    CONFIRMED = "confirmed"
    REFUTED = "refuted"
    INCONCLUSIVE = "inconclusive"
    EXPIRED = "expired"


_TERMINAL = {
    HypothesisStatus.CONFIRMED,
    HypothesisStatus.REFUTED,
    HypothesisStatus.INCONCLUSIVE,
    HypothesisStatus.EXPIRED,
}


@dataclass
class Hypothesis:
    """Hipótese técnica estruturada."""
    hypothesis_id: str
    title: str
    description: str
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    evidence_for: list[str] = field(default_factory=list)
    evidence_against: list[str] = field(default_factory=list)
    confidence: float = 0.5
    source: str = ""                  # "trend", "incident", "observation", "operator"
    related_entities: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    resolved_at: str = ""
    resolution_note: str = ""
    max_evidence: int = 20

    def __post_init__(self) -> None:
        if not self.hypothesis_id or not self.hypothesis_id.strip():
            raise ValueError("hypothesis_id nao pode ser vazio")
        if not self.title or not self.title.strip():
            raise ValueError("title nao pode ser vazio")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence deve estar entre 0 e 1")
        if not self.created_at:
            self.created_at = _utc_now()
        if not self.updated_at:
            self.updated_at = self.created_at

    @property
    def is_terminal(self) -> bool:
        return self.status in _TERMINAL

    @property
    def evidence_balance(self) -> float:
        """Balanço de evidências: positivo favorece, negativo refuta."""
        total = len(self.evidence_for) + len(self.evidence_against)
        if total == 0:
            return 0.0
        return (len(self.evidence_for) - len(self.evidence_against)) / total


class HypothesisEngine:
    """Motor de hipóteses técnicas persistido em JSON.

    Gerencia o ciclo de vida de hipóteses:
    PROPOSED → INVESTIGATING → CONFIRMED | REFUTED | INCONCLUSIVE
    """

    MAX_ACTIVE = 10
    MAX_HISTORY = 50

    def __init__(self, path: Path):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._hypotheses: dict[str, Hypothesis] = {}
        self._load()

    def propose(
        self,
        hypothesis_id: str,
        title: str,
        description: str,
        *,
        source: str = "",
        related_entities: list[str] | None = None,
        initial_evidence: str = "",
    ) -> Hypothesis:
        """Propõe uma nova hipótese. Rejeita se limite ativo excedido."""
        active = sum(1 for h in self._hypotheses.values() if not h.is_terminal)
        if active >= self.MAX_ACTIVE:
            raise OverflowError(f"Limite de {self.MAX_ACTIVE} hipoteses ativas atingido")

        now = _utc_now()
        h = Hypothesis(
            hypothesis_id=hypothesis_id,
            title=title,
            description=description,
            source=source,
            related_entities=related_entities or [],
            created_at=now,
            updated_at=now,
        )
        if initial_evidence:
            h.evidence_for.append(initial_evidence)
        self._hypotheses[hypothesis_id] = h
        self._save()
        return h

    def add_evidence(
        self,
        hypothesis_id: str,
        evidence: str,
        *,
        supports: bool = True,
    ) -> Hypothesis | None:
        """Adiciona evidência a uma hipótese existente."""
        h = self._hypotheses.get(hypothesis_id)
        if h is None or h.is_terminal:
            return None

        target = h.evidence_for if supports else h.evidence_against
        if len(target) >= h.max_evidence:
            return h

        target.append(evidence)
        h.updated_at = _utc_now()

        # Atualizar confidence baseado no balanço
        balance = h.evidence_balance
        h.confidence = max(0.0, min(1.0, 0.5 + balance * 0.3))

        # Auto-transição para INVESTIGATING se ainda PROPOSED
        if h.status == HypothesisStatus.PROPOSED:
            h.status = HypothesisStatus.INVESTIGATING

        self._save()
        return h

    def resolve(
        self,
        hypothesis_id: str,
        status: HypothesisStatus,
        note: str = "",
    ) -> Hypothesis | None:
        """Resolve uma hipótese com status terminal."""
        if status not in _TERMINAL:
            raise ValueError(f"Status {status} nao e terminal")
        h = self._hypotheses.get(hypothesis_id)
        if h is None or h.is_terminal:
            return None
        h.status = status
        h.resolution_note = note
        h.resolved_at = _utc_now()
        h.updated_at = h.resolved_at
        self._save()
        return h

    def get(self, hypothesis_id: str) -> Hypothesis | None:
        return self._hypotheses.get(hypothesis_id)

    def list_active(self) -> list[Hypothesis]:
        return [h for h in self._hypotheses.values() if not h.is_terminal]

    def list_all(self, *, limit: int = 50) -> list[Hypothesis]:
        sorted_h = sorted(self._hypotheses.values(), key=lambda h: h.updated_at, reverse=True)
        return sorted_h[:limit]

    def expire_stale(self, max_age_hours: float = 168.0) -> list[str]:
        """Expira hipóteses ativas sem atualização há mais de max_age_hours."""
        now = datetime.now(timezone.utc)
        expired: list[str] = []
        for h in self._hypotheses.values():
            if h.is_terminal:
                continue
            try:
                updated = datetime.fromisoformat(h.updated_at)
                age_hours = (now - updated).total_seconds() / 3600.0
                if age_hours > max_age_hours:
                    h.status = HypothesisStatus.EXPIRED
                    h.resolved_at = _utc_now()
                    h.updated_at = h.resolved_at
                    h.resolution_note = f"Expirada apos {age_hours:.0f}h sem atualizacao"
                    expired.append(h.hypothesis_id)
            except (ValueError, TypeError):
                pass
        if expired:
            self._save()
        return expired

    def _save(self) -> None:
        # Enforce history limit
        if len(self._hypotheses) > self.MAX_HISTORY:
            terminal = sorted(
                [h for h in self._hypotheses.values() if h.is_terminal],
                key=lambda h: h.resolved_at or h.updated_at,
            )
            while len(self._hypotheses) > self.MAX_HISTORY and terminal:
                oldest = terminal.pop(0)
                del self._hypotheses[oldest.hypothesis_id]

        data = {}
        for hid, h in self._hypotheses.items():
            data[hid] = {
                "hypothesis_id": h.hypothesis_id,
                "title": h.title,
                "description": h.description,
                "status": h.status.value,
                "evidence_for": h.evidence_for,
                "evidence_against": h.evidence_against,
                "confidence": h.confidence,
                "source": h.source,
                "related_entities": h.related_entities,
                "created_at": h.created_at,
                "updated_at": h.updated_at,
                "resolved_at": h.resolved_at,
                "resolution_note": h.resolution_note,
            }
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._path)

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            for hid, item in data.items():
                self._hypotheses[hid] = Hypothesis(
                    hypothesis_id=item["hypothesis_id"],
                    title=item["title"],
                    description=item["description"],
                    status=HypothesisStatus(item["status"]),
                    evidence_for=list(item.get("evidence_for", [])),
                    evidence_against=list(item.get("evidence_against", [])),
                    confidence=float(item.get("confidence", 0.5)),
                    source=str(item.get("source", "")),
                    related_entities=list(item.get("related_entities", [])),
                    created_at=str(item.get("created_at", "")),
                    updated_at=str(item.get("updated_at", "")),
                    resolved_at=str(item.get("resolved_at", "")),
                    resolution_note=str(item.get("resolution_note", "")),
                )
        except (json.JSONDecodeError, TypeError, KeyError):
            pass
