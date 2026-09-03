from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import TextIO

from infrastructure.pentium.atlas.health_engine import assess
from infrastructure.pentium.atlas.journal import JournalError, append_event
from infrastructure.pentium.atlas.reaction_engine import ReactionEngine
from infrastructure.pentium.atlas.state_model import Signal, TechnicalState


_CONFIG_PATH = Path(__file__).with_name("config.json")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate Atlas observed state")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--config", type=Path, default=_CONFIG_PATH)
    parser.add_argument("--journal", type=Path)
    parser.add_argument("--human", action="store_true")
    return parser


def _load_json(path: Path | None, stdin: TextIO) -> dict:
    text = path.read_text(encoding="utf-8") if path else stdin.read()
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("top-level snapshot must be an object")
    return value


def _signals(snapshot: dict) -> tuple[list[Signal], TechnicalState | None]:
    raw_signals = snapshot.get("signals")
    if not isinstance(raw_signals, list):
        raise ValueError("signals must be a list")

    result: list[Signal] = []
    for item in raw_signals:
        if not isinstance(item, dict):
            raise ValueError("signal must be an object")
        source = item.get("source")
        state = item.get("state")
        intensity = item.get("intensity")
        if not isinstance(source, str) or not isinstance(state, str) or not isinstance(intensity, int):
            raise ValueError("signal requires source/state/intensity")
        result.append(
            Signal(
                source=source,
                state=TechnicalState(state),
                intensity=intensity,
                required=bool(item.get("required", True)),
                reason=str(item.get("reason", "")),
            )
        )

    previous_raw = snapshot.get("previous_state")
    previous = TechnicalState(previous_raw) if previous_raw is not None else None
    return result, previous


def _human_line(assessment, decision) -> str:
    reasons = ",".join(assessment.reasons) if assessment.reasons else "none"
    reaction = decision.reaction_id or "silent"
    meme = decision.meme_id or "none"
    return (
        f"state={assessment.state.value} intensity={assessment.intensity} "
        f"reasons={reasons} reaction={reaction} meme={meme}\n"
    )


def main(
    argv: list[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    args = _parser().parse_args(argv)

    try:
        snapshot = _load_json(args.input, stdin)
        signals, previous = _signals(snapshot)
        config = json.loads(args.config.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            raise ValueError("config must be an object")
        assessment = assess(signals, previous)
        engine = ReactionEngine(config, random.Random(0), time.monotonic)
        decision = engine.decide(assessment, ())
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        stderr.write(f"invalid input/config: {exc}\n")
        return 2

    if args.journal is not None:
        try:
            append_event(
                args.journal,
                datetime.now().astimezone().isoformat(timespec="seconds"),
                assessment,
                decision,
            )
        except JournalError as exc:
            stderr.write(f"journal error: {exc}\n")
            return 3

    payload = {
        "assessment": assessment.to_dict(),
        "reaction": decision.to_dict(),
    }

    if args.human:
        stdout.write(_human_line(assessment, decision))
    else:
        stdout.write(json.dumps(payload, sort_keys=True))
        stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
