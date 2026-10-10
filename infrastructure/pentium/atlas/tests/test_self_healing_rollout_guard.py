"""Safety regression: do not enable unattended recovery before inventory certification."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ATLAS_CONFIG = ROOT / "infrastructure" / "pentium" / "atlas" / "config_health_supervisor.json"
AGENT_CONFIG = ROOT / "infrastructure" / "pentium" / "agent" / "config.json"


def test_unverified_managed_targets_remain_read_only():
    cfg = json.loads(AGENT_CONFIG.read_text(encoding="utf-8"))
    for host in cfg["managed_hosts"]:
        assert host["host_id"] in {"x99", "core"}
        assert host.get("allowed_controls", []) == []
        assert host.get("allowed_services", []) == []
        assert host.get("allowed_containers", []) == []


def test_self_healing_rollout_requires_inventory_certification():
    cfg = json.loads(ATLAS_CONFIG.read_text(encoding="utf-8"))
    assert cfg["features"]["health_supervisor_v1"] is True
    assert cfg["features"]["self_healing_v1"] is False
