from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .stimulus_model import Stimulus


class StimulusJournalError(RuntimeError):
    pass


def append_stimulus(
    path: Path,
    stimulus: Stimulus,
    runtime_meta: Mapping[str, Any],
) -> None:
    record = stimulus.to_dict()
    record["runtime_meta"] = dict(runtime_meta)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
            handle.flush()
    except OSError as exc:
        raise StimulusJournalError(str(exc)) from exc
