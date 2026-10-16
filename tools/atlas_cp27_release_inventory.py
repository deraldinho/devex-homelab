"""Atlas CP27 release inventory — read-only.

Inventory of dirty Git paths and hashes with safe bounded output.
Rejects symlinks and path traversal. Never reads file contents or secrets.

Typical usage (command-line):
    python -m tools.atlas_cp27_release_inventory --root /path/to/repo

Typical usage (API):
    from tools.atlas_cp27_release_inventory import inventory
    data = inventory(Path("/path/to/repo"))
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

# Bounded output: maximum number of dirty-file entries to return.
MAX_ENTRIES = 100

# A dirty-line from `git status --porcelain` has the format:
#   XY <path>   where XY are two-character status codes (e.g. " M", "AM", "??")
STATUS_RE = re.compile(r"^(.{2})\s+(.+)$")


def _is_symlink(p: Path) -> bool:
    """Return True if *p* is or points through a symlink."""
    try:
        return p.is_symlink()
    except OSError:
        return False


def _has_path_traversal(p: Path) -> bool:
    """Return True if the path contains directory traversal components."""
    # Inspect the string representation directly; normalize separators
    # so that Windows backslashes are also checked for '..'.
    s = str(p).replace("\\", "/")
    return ".." in s.split("/") or s.startswith("/")


def _safe_path(p: Path) -> bool:
    """Return True if *p* is safe: not a symlink and no path traversal."""
    return not _is_symlink(p) and not _has_path_traversal(p)


def _hash_from_status_line(line: str) -> str:
    """Compute a stable truncated SHA-256 from a git status line.

    We hash the line itself (path + status codes) so we never read file
    contents or secrets. The output is a 16-hex-char truncated digest that
    is still collision-resistant for inventory purposes.
    """
    digest = __import__("hashlib").sha256(line.encode("utf-8")).hexdigest()
    return digest[:16]


def inventory(root: Path, *, offset: int = 0) -> dict:
    """Return a read-only inventory of dirty Git paths and hashes.

    Args:
        root: Path to the repository root directory. Must be an actual
              git repository; otherwise the call is denied.

    Returns:
        dict with keys: "schema_version", "root", "dirty_count",
        "entries" (list of {path, status, hash, classification}),
        "warning".

    Raises:
        ValueError: if *root* is a symlink, not a directory, or not a git
                    repository.
    """
    # --- Validate root and paging before executing any subprocess ---
    if type(offset) is not int or offset < 0:
        raise ValueError("invalid_offset")
    if _is_symlink(root):
        raise ValueError("symlinked_root_forbidden")
    if not root.is_dir():
        raise ValueError("invalid_atlas_root")

    # --- Verify it's a git repository ---
    try:
        git_dir = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=root,
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except subprocess.CalledProcessError as exc:
        raise ValueError("not_a_git_repository") from exc

    # Ensure we operate inside the repo root
    root = Path(git_dir)

    # --- Get dirty paths via git status --porcelain ---
    try:
        raw = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=root,
            stderr=subprocess.DEVNULL,
        ).decode("utf-8", errors="replace")
    except subprocess.CalledProcessError as exc:
        raise ValueError("git_status_failed") from exc

    all_lines = [l for l in raw.splitlines() if l.strip()]
    total_dirty_count = len(all_lines)
    lines = all_lines[offset:offset + MAX_ENTRIES]
    has_more = offset + len(lines) < total_dirty_count
    next_offset = offset + len(lines) if has_more else None

    entries = []
    for line in lines:
        m = STATUS_RE.match(line)
        if not m:
            # Skip malformed lines silently
            continue
        status_codes, path_str = m.group(1), m.group(2)
        p = Path(path_str)

        # Reject symlinks and path traversal
        if not _safe_path(p) or _is_symlink(root / p):
            continue

        # Compute hash from the status line itself (no file contents)
        file_hash = _hash_from_status_line(line)

        # Classification based on git status --porcelain codes
        # Format: XY <path> where XY are two-character status codes
        # e.g. " M" = modified (working dir), "AM" = added+modified, "??" = untracked
        second_code = status_codes[1] if len(status_codes) > 1 else "?"
        first_code = status_codes[0]
        if first_code == " " and second_code == "M":
            classification = "MODIFIED"
        elif first_code == "A" and second_code == "M":
            classification = "ADDED"
        elif first_code == "D" and second_code == " ":
            classification = "DELETED"
        elif first_code == "?" and second_code == "?":
            classification = "UNTRACKED"
        else:
            # Fall back to first character if it's a recognized code
            if first_code in ("M", "A", "D", "?"):
                classification = first_code.upper()
            else:
                classification = "UNKNOWN"

        entries.append(
            {
                "path": path_str,
                "status": status_codes,
                "hash": file_hash,
                "classification": classification,
            }
        )

    dirty_count = len(entries)
    rejected_count = len(lines) - dirty_count

    return {
        "schema_version": 1,
        "root": git_dir,
        "dirty_count": dirty_count,
        "total_dirty_count": total_dirty_count,
        "offset": offset,
        "has_more": has_more,
        "next_offset": next_offset,
        "rejected_count": rejected_count,
        "fingerprint_kind": "status_line_sha256_16",
        "entries": entries,
        "warning": ("Additional pages must be retrieved using --offset."
                    if has_more else ("Some paths were rejected." if rejected_count else None)),
    }


def main(argv=None) -> int:
    """CLI entry-point. Prints JSON inventory and returns exit code."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Atlas CP27 release read-only inventory"
    )
    parser.add_argument(
        "--root",
        type=Path,
        required=True,
        help="Path to the repository root directory",
    )
    parser.add_argument("--offset", type=int, default=0,
                        help="Nonnegative pagination offset; maximum 100 paths per page")
    args = parser.parse_args(argv) if argv is not None else parser.parse_args()

    try:
        data = inventory(args.root, offset=args.offset)
    except (ValueError, OSError):
        print('{"status":"DENIED_INVALID_INPUT"}')
        return 2

    print(json.dumps(data, ensure_ascii=False, indent=2))
    if data["rejected_count"]:
        return 4
    return 3 if data["has_more"] else 0


if __name__ == "__main__":
    sys.exit(main())