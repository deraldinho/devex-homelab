from __future__ import annotations

from collections.abc import Callable
from typing import Any

from infrastructure.pentium.atlas.state_model import GlobalAssessment, ReactionDecision, TechnicalState


class ReactionEngine:
    def __init__(self, config: dict[str, Any], rng: Any, clock: Callable[[], float]):
        self._config = config
        self._rng = rng
        self._clock = clock
        self._last_emitted: dict[str, float] = {}

    @staticmethod
    def _weighted_pick(entries: list[dict[str, Any]], rng: Any) -> str | None:
        weighted = [(entry["id"], max(0.0, float(entry.get("weight", 1)))) for entry in entries]
        total = sum(weight for _, weight in weighted)
        if total <= 0:
            return None
        target = rng.random() * total
        cumulative = 0.0
        for reaction_id, weight in weighted:
            cumulative += weight
            if target < cumulative:
                return reaction_id
        return weighted[-1][0]

    def _meme_for(self, category: str) -> str | None:
        if not self._config.get("memes_enabled", False):
            return None
        entries = self._config.get("meme_pools", {}).get(category, [])
        return self._weighted_pick(entries, self._rng)

    def _on_cooldown(self, category: str, now: float) -> bool:
        seconds = float(self._config.get("cooldowns", {}).get(category, 0))
        last = self._last_emitted.get(category)
        return last is not None and now - last < seconds

    def decide(
        self,
        assessment: GlobalAssessment,
        recent_ids: tuple[str, ...],
    ) -> ReactionDecision:
        category = assessment.state.value
        now = float(self._clock())

        if assessment.state == TechnicalState.CRITICAL:
            self._last_emitted[category] = now
            return ReactionDecision(
                category="critical",
                reaction_id="critical.canonical",
                meme_id=self._meme_for("critical"),
            )

        if self._on_cooldown(category, now):
            return ReactionDecision(category, None, suppressed=True)

        entries = list(self._config.get("reaction_pools", {}).get(category, []))
        recent = set(recent_ids[-int(self._config.get("anti_repeat_window", 0)) :])
        alternatives = [entry for entry in entries if entry.get("id") not in recent]
        if alternatives:
            entries = alternatives

        reaction_id = self._weighted_pick(entries, self._rng)
        if reaction_id is None:
            return ReactionDecision(category, None, suppressed=True)

        self._last_emitted[category] = now
        return ReactionDecision(
            category=category,
            reaction_id=reaction_id,
            meme_id=self._meme_for(category),
        )
