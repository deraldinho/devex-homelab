# Independent orchestration self-audit — 2026-10-15

Evidence: read-only OpenCode v2.0.29 session API and persistent model-state for 3 pre-existing sessions; no new session dispatched.
- architecture ses_ebff53722ffegvvgE0NlEQbwm8: 11 assistant messages, 20 tool calls; includes shell. No terminal final. BLOCKED unauthorized tool observed.
- security ses_ebff53724ffeJF563DOp14v9lB: 9 assistant messages, 18 tool calls; grep,glob,read. No terminal final. PENDING.
- qa ses_ebff41613ffeH4an0n12cHUrh4: 11 assistant messages, 27 tool calls; grep,glob,read. No terminal final. PENDING.
- All 3 persisted as pending with missing session.outcome. OpenCode API does not provide outcome field used by FreeModelFailover. cost 0 is reported but doesn't certify completion.
- Prompt-only readonly instruction did not enforce tool denylist: architecture agent invoked shell. Exact shell action effects not audited.
- New atlas_opencode_session_gate.py and test_atlas_opencode_session_gate.py flag unauthorized tools, reject unfinished tool-call turns and distinguish candidate review from verified result.
- Suite: 338 tests OK (3 skipped) on x99; git diff --check OK.
- This gate is not yet wired into the live dispatcher; production remains BLOCKED. Existing sessions must be reconciled, not blindly restarted.
