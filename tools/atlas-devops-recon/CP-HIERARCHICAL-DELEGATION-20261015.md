# CP hierarchical delegation — 2026-10-15

Evidence: all 3 original OpenCode sessions now API outcome=succeeded, cost=0. Architecture/security/QA reviews recovered to opencode-review/<role>/inspection-report.md. Review findings are advisory, not passing tests or production authorization.

Implementation: atlas_native_delegation.py permits one coordinator to enqueue up to 3 nonduplicate specialist review tasks, with role allowlist, deterministic idempotent outbox and only preapproved free model priorities. No recursive spawning; subagents may not themselves delegate. This is a constrained delegation contract, NOT live automatic launch of subagents. Other model candidates such as a Nemotron 3 Ultra A550B must be verified for exact provider identifier, zero price and API support before use.

Validation: 340 tests OK (3 skipped), git diff --check passed.
Outstanding: real OpenCode worker integration, host-enforced permissions, supervisor heartbeat/terminal extraction, signed session receipt, sandbox and production evidence. Findings from audits must be triaged and corrected.
