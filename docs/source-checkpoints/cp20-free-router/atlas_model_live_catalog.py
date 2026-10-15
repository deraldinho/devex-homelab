"""Read-only OpenCode catalog discovery with explicit pricing attestation.
No model is promoted to free merely because its name ends in '-free'.
"""
from __future__ import annotations
import subprocess
from atlas_model_discovery import build_profiles
from atlas_model_router_adapter import make_free_ranker

def discover_catalog(run=None):
    run=run or (lambda:subprocess.run(["opencode.cmd","models"],
        capture_output=True,text=True,timeout=30,check=True).stdout)
    raw=run()
    return tuple(sorted({line.strip() for line in raw.splitlines()
                         if line.strip().count("/")>=1 and " " not in line.strip()}))

def free_fallback_order(*, trusted_pricing, task, measurements=None, catalog_run=None,
                        allowed=()):
    candidates=build_profiles(discover_catalog(catalog_run),trusted_pricing,measurements)
    return make_free_ranker(candidates,task=task)(allowed)
