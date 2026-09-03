from __future__ import annotations

from infrastructure.pentium.atlas.state_model import GlobalAssessment, Signal, TechnicalState


_SEVERITY = {
    TechnicalState.HEALTHY: 0,
    TechnicalState.ACTIVE: 1,
    TechnicalState.BUSY: 2,
    TechnicalState.DEGRADED: 3,
    TechnicalState.STRESSED: 4,
    TechnicalState.CRITICAL: 5,
}

_PROBLEM_STATES = {
    TechnicalState.DEGRADED,
    TechnicalState.STRESSED,
    TechnicalState.CRITICAL,
}

_NORMAL_STATES = {
    TechnicalState.HEALTHY,
    TechnicalState.ACTIVE,
}


def _reason(signal: Signal) -> str:
    return f"{signal.source}:{signal.reason}" if signal.reason else signal.source


def assess(
    signals: list[Signal],
    previous_state: TechnicalState | None,
) -> GlobalAssessment:
    relevant = [signal for signal in signals if signal.required]
    if not relevant:
        current = TechnicalState.HEALTHY
        intensity = 0
        reasons: tuple[str, ...] = ()
    else:
        current = max(relevant, key=lambda signal: _SEVERITY.get(signal.state, -1)).state
        severity = _SEVERITY[current]
        matching = [signal for signal in relevant if _SEVERITY.get(signal.state, -1) == severity]
        intensity = max((signal.intensity for signal in relevant), default=0)
        reasons = tuple(_reason(signal) for signal in matching)

    recovered = previous_state in _PROBLEM_STATES and current in _NORMAL_STATES
    state = TechnicalState.RECOVERED if recovered else current
    return GlobalAssessment(
        previous_state=previous_state,
        state=state,
        intensity=intensity,
        reasons=reasons,
        recovered=recovered,
    )
