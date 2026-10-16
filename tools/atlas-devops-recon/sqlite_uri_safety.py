"""Canonical SQLite file URI encoding for read-only consumers."""
from pathlib import Path
from urllib.parse import quote

def readonly_uri(path: str | Path, *, immutable: bool = False) -> str:
    resolved = Path(path).resolve(strict=True)
    if not resolved.is_file() or resolved.is_symlink() or Path(path).is_symlink():
        raise ValueError("ledger is not a regular non-symlink file")
    escaped = quote(resolved.as_posix(), safe="/:")
    suffix = "?mode=ro&immutable=1" if immutable else "?mode=ro"
    return "file:" + escaped + suffix
