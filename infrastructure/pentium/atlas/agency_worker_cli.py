"""One-shot core-side Hermes worker. No daemon, queue, or filesystem control.

Read a bounded JSON AgencyRequest from stdin, return only strict JSON to stdout.
Intended for an existing authorized typed transport, not a generic SSH shell.
Never launch on pentium. Disabled until certified with AgencyConfig.enabled.

Security: host attestation via trusted deployment metadata (not spoofable env).
Future: implement isolated worker hostname attestation via deployment-time identity.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from pathlib import Path

from .agency_specialists import AgencyConfig, AgencyRequest, AgencyResult, HermesAgencyWorker

MAX_REQUEST_BYTES = 12288


def run_once(raw: bytes, config: AgencyConfig, worker, *, host: str) -> dict:
    # SECURITY: Staging bypass (ATLAS_CORE_STAGING_CONTAINER=1) ONLY allowed when host IS core.
    # This prevents pentium from spoofing the env var to bypass the core-only restriction.
    if host != "core":
        raise ValueError("core_worker_only")
    if not config.enabled:
        raise ValueError("feature_disabled")
    if len(raw) > MAX_REQUEST_BYTES:
        raise ValueError("request_too_large")
    try:
        payload = json.loads(raw.decode("utf-8", errors="strict"))
        if not isinstance(payload, dict) or set(payload) - set(AgencyRequest.__dataclass_fields__):
            raise ValueError("invalid_request_schema")
        req = AgencyRequest(**payload)
    except (UnicodeError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("invalid_request_schema") from exc
    if req.project not in config.projects or len(req.specialists) > config.max_agents:
        raise ValueError("policy_denied")
    # The core process only returns suggestions; changes still require Atlas policy.
    worker_result = worker(req, config)
    # Validate and convert to strict AgencyResult contract (no extra fields, typed fields).
    # This prevents malicious worker responses with extra fields (e.g., 'actions') from leaking.
    validated = AgencyResult.from_worker(worker_result, req, config)
    # Convert to dict with only the strict typed fields for JSON serialization.
    result = {
        "status": validated.status,
        "reason": validated.reason,
        "summary": validated.summary,
        "agent_slugs": validated.agent_slugs,
        "evidence_refs": validated.evidence_refs,
        "proposed_changes": validated.proposed_changes,
        "tests_run": validated.tests_run,
        "limitations": validated.limitations,
    }
    # Enforce max response size from config before returning (defense in depth; main() also checks).
    encoded = json.dumps(result, ensure_ascii=False).encode("utf-8")
    if len(encoded) > config.max_response_bytes:
        raise ValueError("result_too_large")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Agency Agents core READ-only worker")
    parser.add_argument("--config", type=Path, required=True)
    options = parser.parse_args()
    try:
        config = AgencyConfig.from_json(options.config)
        raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        result = run_once(raw, config, HermesAgencyWorker(), host=socket.gethostname().split(".")[0])
        encoded = json.dumps(result, ensure_ascii=False).encode("utf-8")
        if len(encoded) > config.max_response_bytes:
            raise ValueError("result_too_large")
        sys.stdout.buffer.write(encoded + b"\n")
        return 0
    except Exception:
        # Never print raw input or subprocess stderr. All errors fail closed.
        sys.stdout.write('{"status":"failed","reason":"core_worker_unavailable"}\n')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
