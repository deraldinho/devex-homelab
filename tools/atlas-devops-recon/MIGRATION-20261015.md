# Atlas DevOps checkpoint consolidation — 2026-10-15

Canonical Atlas repository: `C:\Users\deral\DevEx-HomeLab`.

Source checkpoint: `C:\Users\deral\Documents\Atlas-DevOps\CP-ATLAS-RECON-20261015`.

The top-level `.py` and `.md` checkpoint files were copied into `tools/atlas-devops-recon` without overwriting files. Each copied file was checked against its source using SHA-256, with no collisions. Original files are retained while old OpenCode processes may reference the source path. No active Atlas service has been changed, deployed or restarted.

This folder is an isolated integration candidate and is NOT the live Atlas runtime. Existing production code is under `infrastructure/pentium/atlas` and should only be updated after mapping existing functionality, resolving duplicate implementations, TDD, regression checks, permission review, and rollback preparation. Historic logs, archives, credentials and other content under Atlas-DevOps were not migrated.

Next: direct OpenCode agents exclusively to `C:\Users\deral\DevEx-HomeLab`; reconcile old-path sessions; review candidate Python modules for reuse and integrate selectively into the existing architecture.
