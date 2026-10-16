"""Fail-closed static preflight of a generated Hermes Agency Agents plugin.

This code does not import/execute generated Python or enable Hermes plugins.
Plugin generation and installation are separate, gated operations.
"""
from __future__ import annotations

import json
import re
import stat
import sys
from pathlib import Path, PurePosixPath

PLUGIN_REL = Path("source") / "integrations" / "hermes" / "agency-agents-router"
REQUIRED_FILES = ("plugin.yaml", "__init__.py", "data/agents.json")
TOOLS = frozenset({
    "agency_agents_search", "agency_agents_inspect",
    "agency_agents_load", "agency_agents_delegate",
})
SLUG_RE = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,78}[a-z0-9])?\Z")
DIVISION_RE = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")
MAX_JSON_BYTES = 32 * 1024 * 1024
MAX_AGENT_COUNT = 600
MAX_AGENT_BODY = 120_000
# Fields emitted by pinned upstream build-hermes-plugin.py -> parse_agent().
AGENT_FIELDS = frozenset({
    "slug", "name", "description", "division", "color",
    "emoji", "vibe", "source_path", "body",
})


class ValidationError(ValueError):
    pass


def _regular_within(root: Path, target: Path, max_bytes: int) -> str:
    """Reject symlinks at every level before reading a bounded regular file."""
    try:
        rel = target.relative_to(root)
    except ValueError as exc:
        raise ValidationError("path_outside_stage") from exc
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise ValidationError("symlink_forbidden")
    try:
        resolved = target.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
        meta = target.lstat()
    except (OSError, ValueError) as exc:
        raise ValidationError("missing_or_outside_file") from exc
    if not stat.S_ISREG(meta.st_mode):
        raise ValidationError("not_regular_file")
    if not 0 < meta.st_size <= max_bytes:
        raise ValidationError("invalid_file_size")
    try:
        return target.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValidationError("invalid_file_encoding") from exc


def _manifest_tools(text: str) -> tuple[str, ...]:
    """Parse the simple YAML emitted by the pinned upstream builder.

    This deliberately isn't a general-purpose YAML parser. Generated YAML
    outside the known profile fails closed rather than being executed.
    """
    lines = text.splitlines()
    names: list[str] = []
    tools: list[str] = []
    in_tools = False
    tool_sections = 0
    for line in lines:
        stripped = line.strip()
        if not line.startswith((" ", "\t")):
            in_tools = False
            if line.startswith("name:"):
                names.append(line.split(":", 1)[1].strip())
            if line.startswith("provides_tools:"):
                tool_sections += 1
                if stripped != "provides_tools:":
                    raise ValidationError("inline_tools_forbidden")
                in_tools = True
            # Extra top-level fields are allowed (version, description).
        elif in_tools and stripped:
            if not re.fullmatch(r"-\s+agency_agents_[a-z_]+", stripped):
                raise ValidationError("invalid_tool_entry")
            tools.append(stripped[1:].strip())
    if names != ["agency-agents-router"] or tool_sections != 1:
        raise ValidationError("manifest_name_or_section_invalid")
    if len(tools) != len(TOOLS) or set(tools) != TOOLS:
        raise ValidationError("manifest_tools_missing_duplicate_or_extra")
    return tuple(tools)


def _agents(text: str) -> int:
    try:
        data = json.loads(text)
    except (ValueError, TypeError) as exc:
        raise ValidationError("invalid_agent_json") from exc
    if not isinstance(data, list) or not (1 <= len(data) <= MAX_AGENT_COUNT):
        raise ValidationError("agent_count_invalid")
    seen = set()
    for obj in data:
        if not isinstance(obj, dict) or not AGENT_FIELDS.issubset(obj):
            raise ValidationError("agent_schema_invalid")
        if not all(isinstance(obj[k], str) for k in AGENT_FIELDS):
            raise ValidationError("agent_field_type_invalid")
        slug, division, body = obj["slug"], obj["division"], obj["body"]
        if not SLUG_RE.fullmatch(slug) or slug in seen:
            raise ValidationError("duplicate_or_invalid_slug")
        seen.add(slug)
        if not DIVISION_RE.fullmatch(division):
            raise ValidationError("invalid_division")
        if not body.strip() or len(body) > MAX_AGENT_BODY:
            raise ValidationError("invalid_agent_body")
        source = obj["source_path"]
        posix = PurePosixPath(source)
        if (not source or "\\" in source or ":" in source or posix.is_absolute()
                or ".." in posix.parts or len(source) > 512):
            raise ValidationError("invalid_agent_source_path")
        if any(len(obj[k]) > 5000 for k in ("name", "description", "color", "emoji", "vibe")):
            raise ValidationError("agent_metadata_too_large")
    return len(data)


def validate_plugin_staging(staging_root: str | Path) -> dict[str, object]:
    root = Path(staging_root)
    if not root.is_absolute() or not root.is_dir() or root.is_symlink():
        raise ValidationError("staging_root_invalid")
    # Canonical production of convert.sh --tool hermes lives under source/.
    plugin = root / PLUGIN_REL
    if not plugin.is_dir():
        raise ValidationError("generated_plugin_missing")
    for rel in REQUIRED_FILES:
        path = plugin / rel
        # _regular_within checks ancestors and leaf symlinks and bounded content.
        limit = MAX_JSON_BYTES if rel == "data/agents.json" else 250_000
        contents = _regular_within(root, path, limit)
        if rel == "plugin.yaml":
            tools = _manifest_tools(contents)
        elif rel == "data/agents.json":
            count = _agents(contents)
    return {
        "valid": True,
        "plugin_path": str(plugin),
        "tools": list(tools),
        "agent_count": count,
    }


def main(args: list[str] | None = None) -> int:
    args = sys.argv[1:] if args is None else args
    if len(args) != 1:
        print("usage: plugin_validator.py ABSOLUTE_NEW_STAGE_ROOT", file=sys.stderr)
        return 2
    try:
        result = validate_plugin_staging(args[0])
    except ValidationError as exc:
        print("STAGE_VALIDATION_FAILED: " + str(exc), file=sys.stderr)
        return 1
    print("STAGE_VALIDATED agents=" + str(result["agent_count"]) +
          " tools=" + str(len(result["tools"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
