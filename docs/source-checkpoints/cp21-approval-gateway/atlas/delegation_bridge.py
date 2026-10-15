"""Durable, approval-gated delegation proposals for Atlas -> x99 OpenCode.

Proposing never grants permission to execute. The x99 operator explicitly
approves each task in the separate local execution bridge.
"""
from __future__ import annotations
import json, os, re, sys, uuid, hashlib, hmac
from contextlib import contextmanager
from datetime import datetime, timezone
if os.name == 'nt':
    import msvcrt
else:
    import fcntl
from pathlib import Path

STATE_ROOT = Path.home() / "pentium-agent" / "atlas" / "runtime" / "delegation"
_STATES = frozenset(("awaiting_approval", "running", "pending", "completed", "blocked", "failed"))
_TERMINAL = frozenset(("completed", "blocked", "failed"))
_RECEIPT_FIELDS = ("task_id", "state", "model", "reason", "session_id", "nonce", "sent_at")

def _safe_origin(route):
    if not isinstance(route, dict) or route.get("channel") != "discord":
        return None
    channel = str(route.get("reply_target") or "")
    actor = str(route.get("actor_id") or "")
    source_id = str(route.get("client_message_id") or "")
    if not (channel.isdigit() and actor.isdigit() and source_id.startswith("discord:")
            and source_id[8:].isdigit() and len(channel) <= 22 and len(actor) <= 22
            and len(source_id) <= 32):
        return None
    return {"channel": "discord", "reply_target": channel,
            "actor_id": actor, "client_message_id": source_id}


def _receipt_body(item: dict) -> bytes:
    if not all(isinstance(item.get(field), str) for field in _RECEIPT_FIELDS):
        raise ValueError("receipt fields incomplete")
    data = {name: item[name] for name in _RECEIPT_FIELDS}
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

_ID_RE = re.compile(r"^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$")
_AREA_RE = re.compile(r"^[a-z][a-z0-9_-]{0,39}$")

def _write_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(temp, path)

class DelegationBridge:
    def __init__(self, root: Path = STATE_ROOT):
        self.root = Path(root)
        self.outbox = self.root / "outbox"
        self.results = self.root / "results"
        self.notifications = self.root / "notifications"
        self.deliveries = self.root / "deliveries"

    def _report_key(self) -> bytes | None:
        path = self.root / "worker-report.key"
        if not path.is_file():
            return None
        key = path.read_bytes()
        if len(key) != 32:
            raise ValueError("invalid worker report key")
        return key

    def _verified_signature(self, item: dict) -> bool:
        try:
            key = self._report_key()
            sig = item.get("signature")
            if key is None or not isinstance(sig, str) or len(sig) != 64:
                return False
            digest = hmac.new(key, _receipt_body(item), hashlib.sha256).hexdigest()
            return hmac.compare_digest(digest, sig)
        except (ValueError, TypeError, OSError):
            return False

    def read_verified_result(self, task_id: str) -> dict | None:
        """Return only an authenticated worker receipt. Legacy records stay readable but untrusted."""
        result = self.read_result(task_id)
        return result if result is not None and self._verified_signature(result) else None

    @contextmanager
    def _task_lock(self, task_id: str):
        """Serialize cancellation and worker reports by task ID on this host."""
        lock_path = self.root / "locks" / (task_id + ".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+b") as handle:
            handle.seek(0, 2)
            if handle.tell() == 0:
                handle.write(b" ")
                handle.flush()
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                handle.seek(0)
                if os.name == "nt":
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def propose(self, item, *, source_origin=None) -> dict:
        task_id = str(item.item_id)
        if not _ID_RE.fullmatch(task_id):
            raise ValueError("task_id must be UUID")
        with self._task_lock(task_id):
            return self._propose_locked(item, source_origin=source_origin)

    def _propose_locked(self, item, *, source_origin=None) -> dict:
        task_id = str(item.item_id)
        if not _ID_RE.fullmatch(task_id):
            raise ValueError("task_id must be UUID")
        objective = str(item.objective).strip()
        area = str(item.area).strip().lower()
        if not 15 <= len(objective) <= 2000 or not _AREA_RE.fullmatch(area):
            raise ValueError("delegation objective or area invalid")
        target = self.outbox / f"{task_id}.json"
        proposal = {
            "schema_version": 1, "task_id": task_id, "objective": objective,
            "area": area, "origin": "atlas_task_create",
            "state": "awaiting_approval",
            "created_at": str(item.created_at),
        }
        route = _safe_origin(source_origin)
        if route is not None:
            proposal["source_origin"] = route
        if target.exists():
            existing = json.loads(target.read_text(encoding="utf-8"))
            if existing != proposal:
                raise ValueError("duplicate task_id with conflicting payload")
            return existing
        _write_atomic(target, proposal)
        return proposal

    def block_proposal(self, task_id: str, reason: str = "local_transition_failed") -> bool:
        if not _ID_RE.fullmatch(str(task_id)):
            raise ValueError("invalid task id")
        with self._task_lock(task_id):
            return self._block_proposal_locked(task_id, reason)

    def _block_proposal_locked(self, task_id: str, reason: str) -> bool:
        """Invalidate an external proposal so the worker cannot approve/execute it."""
        if not _ID_RE.fullmatch(str(task_id)):
            raise ValueError("invalid task id")
        target = self.outbox / f"{task_id}.json"
        if not target.is_file():
            raise ValueError("missing proposal requires reconciliation")
        proposal = json.loads(target.read_text(encoding="utf-8"))
        if proposal.get("task_id") != task_id or proposal.get("origin") != "atlas_task_create":
            raise ValueError("invalid proposal identity")
        if proposal.get("state") not in {"awaiting_approval", "blocked"}:
            raise ValueError("unexpected proposal state")
        active = self.read_result(task_id)
        if active is not None and active["state"] in {"running", "pending", "completed"}:
            raise ValueError("external execution in progress or already completed")
        if proposal["state"] == "blocked":
            return True
        proposal["state"] = "blocked"
        proposal["block_reason"] = str(reason)[:80]
        _write_atomic(target, proposal)
        return True

    def list_pending(self) -> list[dict]:
        if not self.outbox.is_dir():
            return []
        results=[]
        for path in sorted(self.outbox.glob("*.json"))[:500]:
            if not _ID_RE.fullmatch(path.stem) or path.stat().st_size > 8192:
                continue
            try:
                item=json.loads(path.read_text(encoding="utf-8"))
                if item.get("schema_version") != 1 or item.get("task_id") != path.stem:
                    continue
                if item.get("origin") != "atlas_task_create" or item.get("state") != "awaiting_approval":
                    continue
                if not _AREA_RE.fullmatch(str(item.get("area", ""))):
                    continue
                results.append(item)
            except (ValueError, OSError, TypeError):
                continue
        return results

    def read_result(self, task_id: str) -> dict | None:
        if not _ID_RE.fullmatch(str(task_id)):
            return None
        target=self.results/f"{task_id}.json"
        proposal_path = self.outbox / f"{task_id}.json"
        try:
            proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
            if proposal.get("task_id") != task_id or proposal.get("origin") != "atlas_task_create":
                return None
            item=json.loads(target.read_text(encoding="utf-8"))
            if item.get("task_id")==task_id and item.get("state") in _STATES:
                return item
        except (OSError,ValueError,TypeError):
            return None
        return None

    def latest_result(self) -> dict | None:
        if not self.results.is_dir():
            return None
        paths=sorted(self.results.glob("*.json"),
                     key=lambda p:p.stat().st_mtime, reverse=True)[:30]
        for path in paths:
            outcome=self.read_result(path.stem)
            if outcome:
                return outcome
        return None

    def write_result(self, item: dict) -> dict:
        task_id = str(item.get("task_id") or "")
        if not _ID_RE.fullmatch(task_id):
            raise ValueError("invalid task_id")
        with self._task_lock(task_id):
            return self._write_result_locked(item)

    def _write_result_locked(self, item: dict) -> dict:
        task_id=str(item.get("task_id") or "")
        if not _ID_RE.fullmatch(task_id):
            raise ValueError("invalid task_id")
        try:
            proposal = json.loads((self.outbox / f"{task_id}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            raise ValueError("result has no matching Atlas task")
        if proposal.get("task_id") != task_id or proposal.get("origin") != "atlas_task_create":
            raise ValueError("result has mismatching task identity")
        state=str(item.get("state") or "")
        proposal_state = proposal.get("state")
        if proposal_state not in {"awaiting_approval", "blocked"}:
            raise ValueError("invalid proposal state")
        if proposal_state == "blocked" and state != "blocked":
            raise ValueError("blocked proposal cannot be executed")
        if state not in _STATES:
            raise ValueError("invalid result state")
        model=str(item.get("model") or "")
        reason=str(item.get("reason") or "")
        session_id=str(item.get("session_id") or "")
        if len(model) > 100 or len(reason) > 200 or len(session_id) > 200:
            raise ValueError("oversized signed result field")
        if state=="completed" and not session_id:
            raise ValueError("completed requires a session id")
        key = self._report_key()
        if key is None:
            raise ValueError("worker report key required; unsigned reports disabled")
        if key is not None:
            if not self._verified_signature(item):
                raise ValueError("unauthenticated worker report")
            nonce = str(item.get("nonce") or "")
            if len(nonce) != 32 or not re.fullmatch(r"[0-9a-f]{32}", nonce):
                raise ValueError("invalid receipt nonce")
            try:
                sent_time = datetime.fromisoformat(str(item.get("sent_at") or ""))
                if sent_time.tzinfo is None or abs((datetime.now(timezone.utc) - sent_time).total_seconds()) > 900:
                    raise ValueError("expired or future receipt")
            except (ValueError, TypeError):
                raise ValueError("invalid or stale receipt timestamp")
        existing=self.read_result(task_id)
        if key is not None and existing is not None and existing["state"] not in _TERMINAL:
            if existing.get("signature") == item.get("signature"):
                return existing  # idempotent duplicate, no second transition
            prior = existing.get("sent_at")
            if prior:
                try:
                    previous_time = datetime.fromisoformat(prior)
                    if sent_time <= previous_time:
                        raise ValueError("out-of-order authenticated report")
                except (TypeError, ValueError):
                    raise ValueError("out-of-order authenticated report")
        if existing is not None and existing["state"] in _TERMINAL:
            # Terminal results are immutable. A duplicate acknowledgement is safe,
            # but a delayed running/pending response must never downgrade success.
            if all((existing["state"]==state,
                    existing.get("model", "")==model,
                    existing.get("reason", "")==reason,
                    existing.get("session_id", "")==session_id)):
                return existing
            raise ValueError("terminal delegation result cannot be overwritten")
        result={"schema_version":1,"task_id":task_id,"state":state,
                "model":model,"reason":reason,"session_id":session_id,
                "nonce":str(item.get("nonce") or ""),
                "sent_at":str(item.get("sent_at") or ""),
                "signature":str(item.get("signature") or ""),
                "updated_at":datetime.now(timezone.utc).isoformat()}
        _write_atomic(self.results/f"{task_id}.json",result)
        return result

def main() -> int:
    bridge=DelegationBridge()
    action=sys.argv[1] if len(sys.argv)>1 else ""
    if action=="list":
        print(json.dumps(bridge.list_pending(),ensure_ascii=False))
        return 0
    if action=="report":
        raw=sys.stdin.read(8193)
        if len(raw)>8192:
            return 2
        try:
            result=bridge.write_result(json.loads(raw))
            print(json.dumps(result,ensure_ascii=False))
            return 0
        except (ValueError,TypeError):
            return 2
    if action=="status":
        print(json.dumps(bridge.latest_result(),ensure_ascii=False))
        return 0
    return 2

if __name__=="__main__":
    raise SystemExit(main())
