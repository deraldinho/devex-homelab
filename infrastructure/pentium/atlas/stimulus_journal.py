from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from .stimulus_model import Stimulus


DEFAULT_MAX_RECORDS = 8192
DEFAULT_MAX_BYTES = 8 * 1024 * 1024
COMPACTION_TARGET_RATIO = 0.75


class StimulusJournalError(RuntimeError):
    pass

def _safe_unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _journal_state(path: Path) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    size = path.stat().st_size
    with path.open("rb") as handle:
        count = sum(1 for _ in handle)
    return count, size


def _write_compacted(path: Path, lines: list[bytes], max_records: int, max_bytes: int) -> None:
    target_records = max(1, int(max_records * COMPACTION_TARGET_RATIO))
    target_bytes = max(1, int(max_bytes * COMPACTION_TARGET_RATIO))
    start = max(0, len(lines) - target_records)
    total = sum(len(line) for line in lines[start:])
    while total > target_bytes and start < len(lines) - 1:
        total -= len(lines[start])
        start += 1
    selected = lines[start:]
    temp = path.with_name(path.name + ".tmp")
    try:
        with temp.open("wb") as handle:
            for line in selected:
                handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        _safe_unlink(temp)


def append_stimulus(
    path: Path,
    stimulus: Stimulus,
    runtime_meta: Mapping[str, Any],
    *,
    max_records: int = DEFAULT_MAX_RECORDS,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> None:
    if max_records <= 0 or max_bytes <= 0:
        raise ValueError("journal bounds must be > 0")
    record = stimulus.to_dict()
    record["runtime_meta"] = dict(runtime_meta)
    encoded = (json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    if len(encoded) > max_bytes:
        raise StimulusJournalError("serialized stimulus exceeds max_bytes")

    path = Path(path)
    temp = path.with_name(path.name + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        count, size = _journal_state(path)
        if count + 1 <= max_records and size + len(encoded) <= max_bytes:
            with path.open("ab") as handle:
                handle.write(encoded)
                handle.flush()
            return

        lines = []
        if path.exists():
            with path.open("rb") as handle:
                lines = handle.readlines()
        lines.append(encoded)
        _write_compacted(path, lines, max_records, max_bytes)
    except OSError as exc:
        _safe_unlink(temp)
        raise StimulusJournalError(str(exc)) from exc
