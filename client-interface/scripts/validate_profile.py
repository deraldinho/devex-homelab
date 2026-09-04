#!/usr/bin/env python3
"""Validate L2jToren client-interface profiles and optional manifests.

This validator intentionally has no third-party dependencies so it can run in CI
and on a clean workstation before any proprietary client file is opened.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
HEX_DWORD_RE = re.compile(r"^0x[0-9A-Fa-f]{8}$")
PROHIBITED_EXTENSIONS = {
    ".7z",
    ".bin",
    ".dll",
    ".exe",
    ".iso",
    ".pak",
    ".rar",
    ".u",
    ".utx",
    ".xdat",
    ".zip",
}


class ValidationError(ValueError):
    """Raised when a profile or manifest violates the contract."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON in {path}: {exc}") from exc

    if not isinstance(value, dict):
        raise ValidationError(f"root value must be an object: {path}")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def validate_optional_sha256(value: Any, field: str) -> None:
    if value is None:
        return
    require(isinstance(value, str), f"{field} must be a string or null")
    require(bool(SHA256_RE.fullmatch(value)), f"{field} must be lowercase SHA-256")


def validate_profile(profile: dict[str, Any]) -> None:
    require(profile.get("schemaVersion") == 1, "schemaVersion must be 1")
    require(profile.get("profileId") == "interlude-746-l2jtoren", "unexpected profileId")
    require(profile.get("chronicle") == "Interlude", "chronicle must be Interlude")

    revision = profile.get("clientRevision")
    require(isinstance(revision, dict), "clientRevision must be an object")
    require(revision.get("gameProtocol") == 746, "gameProtocol must be 746")
    login_protocol = revision.get("loginInitProtocol")
    require(
        isinstance(login_protocol, str) and bool(HEX_DWORD_RE.fullmatch(login_protocol)),
        "loginInitProtocol must be an eight-digit hexadecimal DWORD",
    )
    require(revision.get("xdatSchema") == "ct0", "xdatSchema must be ct0 for Interlude")

    tooling = profile.get("tooling")
    require(isinstance(tooling, dict), "tooling must be an object")
    editor = tooling.get("xdatEditor")
    require(isinstance(editor, dict), "tooling.xdatEditor must be an object")
    require(editor.get("repository") == "nascimentolh/XDAT_NEW", "unexpected XDAT editor")
    commit = editor.get("commit")
    require(isinstance(commit, str) and bool(COMMIT_RE.fullmatch(commit)), "invalid XDAT commit")
    require(editor.get("license") == "MIT", "XDAT editor license must be recorded as MIT")
    require(
        isinstance(editor.get("minimumJavaVersion"), int)
        and editor["minimumJavaVersion"] >= 21,
        "minimumJavaVersion must be at least 21",
    )

    baseline = profile.get("baseline")
    require(isinstance(baseline, dict), "baseline must be an object")
    for key, entry in baseline.items():
        require(isinstance(entry, dict), f"baseline.{key} must be an object")
        require(isinstance(entry.get("fileName"), str), f"baseline.{key}.fileName is required")
        validate_optional_sha256(entry.get("sha256"), f"baseline.{key}.sha256")

    policy = profile.get("policy")
    require(isinstance(policy, dict), "policy must be an object")
    require(policy.get("commitClientBinaries") is False, "client binaries must not be committed")
    require(policy.get("commitEditedXdat") is False, "edited Interface.xdat must not be committed")
    require(policy.get("requireSha256Manifest") is True, "SHA-256 manifest must be required")
    require(policy.get("requireBaselineBackup") is True, "baseline backup must be required")
    require(
        policy.get("requireDisposableTestSystem") is True,
        "a disposable test System must be required",
    )


def validate_manifest(manifest: dict[str, Any], profile: dict[str, Any]) -> None:
    require(manifest.get("schemaVersion") == 1, "manifest schemaVersion must be 1")
    require(manifest.get("profileId") == profile.get("profileId"), "manifest profileId mismatch")
    require(isinstance(manifest.get("generatedAtUtc"), str), "generatedAtUtc is required")

    files = manifest.get("files")
    require(isinstance(files, list) and files, "manifest files must be a non-empty array")

    seen: set[str] = set()
    for index, entry in enumerate(files):
        prefix = f"files[{index}]"
        require(isinstance(entry, dict), f"{prefix} must be an object")
        name = entry.get("fileName")
        require(isinstance(name, str) and name, f"{prefix}.fileName is required")
        require(name not in seen, f"duplicate manifest entry: {name}")
        seen.add(name)
        require(isinstance(entry.get("sizeBytes"), int) and entry["sizeBytes"] >= 0, f"{prefix}.sizeBytes invalid")
        validate_optional_sha256(entry.get("sha256"), f"{prefix}.sha256")
        require(entry.get("sha256") is not None, f"{prefix}.sha256 is required")

        pe = entry.get("pe")
        if pe is not None:
            require(isinstance(pe, dict), f"{prefix}.pe must be an object or null")
            require(isinstance(pe.get("machine"), str), f"{prefix}.pe.machine is required")
            require(isinstance(pe.get("timeDateStamp"), int), f"{prefix}.pe.timeDateStamp is required")
            require(isinstance(pe.get("sizeOfImage"), int), f"{prefix}.pe.sizeOfImage is required")


def scan_repository(root: Path) -> list[Path]:
    violations: list[Path] = []
    ignored_parts = {".git", ".idea", ".metadata", "build", "bin", "target"}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in ignored_parts for part in path.parts):
            continue
        if path.suffix.lower() in PROHIBITED_EXTENSIONS:
            violations.append(path)
    return violations


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--scan-root", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        profile = load_json(args.profile)
        validate_profile(profile)
        if args.manifest:
            validate_manifest(load_json(args.manifest), profile)
        if args.scan_root:
            violations = scan_repository(args.scan_root)
            require(
                not violations,
                "proprietary client artifacts found in repository: "
                + ", ".join(str(path) for path in violations),
            )
    except ValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"OK: {args.profile}")
    if args.manifest:
        print(f"OK: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
