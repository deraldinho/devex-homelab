"""Offline CP-SENTRY-P0 benchmark: prompt exposure, NOT real LLM task success.

Seeded 30%-fault scenario; compare NONE/ALL/CONDITIONAL lesson policies.
No network/model/provider. Writes only temporary SQLite and optional JSON.
Run: py -m tools.benchmark_failure_memory --events 200 --output PATH
"""
from __future__ import annotations

import argparse
import json
import math
import random
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from infrastructure.pentium.atlas.failure_memory import FailureMemory
from infrastructure.pentium.atlas.health_supervisor import (
    EvaluatedComponentHealth, SupervisorSnapshot,
)
from infrastructure.pentium.atlas.health_supervisor_model import ComponentHealthState as State

BASE = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)
COMPONENTS = (
    "atlas-cognitive.service", "atlas-discord.service",
    "atlas-dashboard.service", "atlas-observation.service",
)


def make_snapshot(component, state, minute):
    now = (BASE + timedelta(minutes=minute)).isoformat()
    obj = EvaluatedComponentHealth(
        component, "pentium", "running", state, now,
        ("synthetic_failure_injection",), ("fixture:synthetic",), True,
    )
    return SupervisorSnapshot(now, state, (obj,))


def percentile_95(measurements):
    values = sorted(measurements)
    return round(values[math.ceil(len(values) * .95) - 1] / 1_000_000, 6)


def run(events=200, rate=0.30):
    if not isinstance(events, int) or events < 30:
        raise ValueError("events must be >=30")
    if not 0 < rate < 1:
        raise ValueError("rate must be between 0 and 1")
    rng = random.Random(261016)
    with tempfile.TemporaryDirectory() as tmp:
        memory = FailureMemory(Path(tmp) / "sentry.sqlite3")
        try:
            seed_lessons = []
            for j, component in enumerate(COMPONENTS):
                minute = j * 4
                opened = memory.observe_snapshot(make_snapshot(component, State.FAILED, minute))
                inc_id = opened[0]["incident_id"]
                memory.observe_snapshot(make_snapshot(component, State.HEALTHY, minute + 1))
                memory.observe_snapshot(make_snapshot(component, State.HEALTHY, minute + 2))
                text = f"Check isolated health probe for {component} before retry"
                result = memory.record_verified_lesson(
                    incident_id=inc_id, cause="isolated fixture timeout",
                    correction=text, verification_refs=(f"fixture:{j}:green",),
                    verifier=lambda incident, refs: incident["state"] == "recovered"
                    and len(refs) == 1,
                    at=(BASE + timedelta(minutes=minute + 3)).isoformat(),
                )
                seed_lessons.append({"lesson_id": result["lesson_id"],
                                     "correction": text, "cause": "isolated fixture timeout",
                                     "authority": "evidence_only"})
            arms = {name: {"bytes": 0, "false_exposures": 0, "fault_coverage": 0,
                           "latency_ms": []} for name in ("none", "all", "conditional")}
            # Exact seeded injection ratio (not a binomial approximation).
            faulty_indices = set(rng.sample(range(events), round(events * rate)))
            fault_count = 0
            for index in range(events):
                component = COMPONENTS[index % len(COMPONENTS)]
                minute = 32 + index * 4
                failed = index in faulty_indices
                current = memory.observe_snapshot(
                    make_snapshot(component, State.FAILED if failed else State.HEALTHY, minute))
                incident_id = current[0]["incident_id"] if failed else None
                if failed:
                    fault_count += 1
                for name in arms:
                    t0 = time.perf_counter_ns()
                    if name == "none":
                        suggestions = ()
                    elif name == "all":
                        suggestions = tuple(seed_lessons)
                    else:
                        suggestions = memory.advice_for_incident(
                            incident_id, at=(BASE + timedelta(minutes=minute)).isoformat()
                        ) if incident_id else ()
                    elapsed = time.perf_counter_ns() - t0
                    encoded = json.dumps(suggestions, ensure_ascii=False).encode("utf-8")
                    arms[name]["bytes"] += len(encoded) if suggestions else 0
                    arms[name]["latency_ms"].append(elapsed)
                    arms[name]["false_exposures"] += int(bool(suggestions) and not failed)
                    arms[name]["fault_coverage"] += int(bool(suggestions) and failed)
                if failed:
                    memory.observe_snapshot(make_snapshot(component, State.HEALTHY, minute + 1))
                    memory.observe_snapshot(make_snapshot(component, State.HEALTHY, minute + 2))
            data = {
                "benchmark": "atlas_sentry_isolated_synthetic",
                "scope": "memory_context_exposure_only; no LLM inference or repairs",
                "seed": 261016, "events": events,
                "fault_rate_requested": rate,
                "faults_injected": fault_count,
                "lessons_verified_seeded": memory.stats()["lessons"],
                "arms": {},
            }
            for name, arm in arms.items():
                data["arms"][name] = {
                    "context_bytes": arm["bytes"],
                    "estimated_tokens_upper_4bytes": math.ceil(arm["bytes"] / 4),
                    "false_exposures_healthy": arm["false_exposures"],
                    "failures_with_advice": arm["fault_coverage"],
                    "retrieval_latency_p95_ms": percentile_95(arm["latency_ms"]),
                }
            return data
        finally:
            memory.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=int, default=200)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(events=args.events)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
