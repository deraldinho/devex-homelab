from __future__ import annotations

import json
from pathlib import Path

from infrastructure.pentium.atlas.state_model import GlobalAssessment, ReactionDecision


class JournalError(RuntimeError):
    pass


def append_event(
    path: Path,
    timestamp: str,
    assessment: GlobalAssessment,
    decision: ReactionDecision,
) -> None:
    record = {
        "timestamp": timestamp,
        "previous_state": assessment.previous_state.value if assessment.previous_state else None,
        "state": assessment.state.value,
        "intensity": assessment.intensity,
        "reasons": list(assessment.reasons),
        "reaction_category": decision.category,
        "reaction_id": decision.reaction_id,
        "meme_id": decision.meme_id,
    }

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
            handle.flush()
    except OSError as exc:
        raise JournalError(str(exc)) from exc
