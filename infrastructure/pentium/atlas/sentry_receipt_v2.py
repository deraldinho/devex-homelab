"""CP-SENTRY-P3: Ed25519 attestations from separately isolated trusted producers.

Signers belong in executor/health service processes and never in a language
model capability. Consumer has public keys only; no repair/tool dispatch.
"""
from __future__ import annotations

import base64
import json
import os
import re
import stat
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    load_pem_private_key, Encoding, PublicFormat,
)

from .failure_memory import FailureMemory, FailureMemoryError
from .health_supervisor import SupervisorSnapshot
from .health_supervisor_model import ComponentHealthState as State

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z", re.ASCII)
_PAYLOAD_FIELDS = frozenset({
    "version", "algorithm", "issuer", "key_id", "receipt_id", "incident_id",
    "component", "host", "action_id", "event_at", "operation", "target",
    "status", "authorized", "evidence_ref",
})
_FULL_FIELDS = _PAYLOAD_FIELDS | {"signature"}
_MAX_RECEIPT = 2048


class ReceiptV2Error(FailureMemoryError):
    """Invalid independent evidence; fail-closed without exposing contents."""


def _valid_id(value):
    return type(value) is str and bool(_ID.fullmatch(value))


def _instant(text):
    if not isinstance(text, str) or len(text) > 48:
        raise ReceiptV2Error("invalid_timestamp")
    try:
        value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReceiptV2Error("invalid_timestamp") from exc
    if value.tzinfo is None or value.utcoffset() is None:
        raise ReceiptV2Error("naive_timestamp")
    return value.astimezone(timezone.utc)


def _canonical(obj):
    try:
        return json.dumps(obj,sort_keys=True,separators=(",",":"),
                          ensure_ascii=True,allow_nan=False).encode("ascii")
    except (ValueError, TypeError, OverflowError) as exc:
        raise ReceiptV2Error("invalid_encoding") from exc


def _validate(data):
    if type(data) is not dict or set(data) != _PAYLOAD_FIELDS:
        raise ReceiptV2Error("invalid_schema")
    if type(data["version"]) is not int or data["version"] != 2 or data["algorithm"] != "Ed25519":
        raise ReceiptV2Error("invalid_version")
    if data["issuer"] not in ("executor", "health_probe"):
        raise ReceiptV2Error("invalid_role")
    if any(not _valid_id(data[name]) for name in (
        "key_id","receipt_id","incident_id","component","host",
        "action_id","target","evidence_ref"
    )):
        raise ReceiptV2Error("invalid_identifier")
    if data["target"] != data["component"] or type(data["authorized"]) is not bool:
        raise ReceiptV2Error("target_mismatch")
    if data["issuer"] == "executor":
        if (data["operation"] not in ("restart_service","start_service")
                or data["status"] != "success" or not data["authorized"]):
            raise ReceiptV2Error("unauthorized_execution")
    else:
        if (data["operation"] != "observe" or data["status"] != "healthy"
                or data["authorized"]):
            raise ReceiptV2Error("unauthorized_probe")
    _instant(data["event_at"])
    if len(_canonical(data)) > _MAX_RECEIPT:
        raise ReceiptV2Error("oversized_receipt")


class Ed25519ReceiptSigner:
    def __init__(self,role,key_id,private_key,*,expected_role=None):
        if role not in ("executor","health_probe") or (
            expected_role is not None and role != expected_role
        ):
            raise ValueError("signer_role_invalid")
        if not _valid_id(key_id) or not isinstance(private_key, Ed25519PrivateKey):
            raise ValueError("signer_private_key_invalid")
        self.role=role
        self.key_id=key_id
        self.__private_key=private_key

    def public_key(self):
        return self.__private_key.public_key()

    def sign_blob(self, payload: bytes) -> bytes:
        # Only the independent health publisher signs the bounded manifest.
        if self.role != "health_probe" or type(payload) is not bytes or len(payload)>8192:
            raise ReceiptV2Error("manifest_signing_forbidden")
        return self.__private_key.sign(payload)

    def sign(self,*,incident_id,component,host,action_id,event_at,operation,status,
             authorized,evidence_ref):
        body={
            "version":2,"algorithm":"Ed25519","issuer":self.role,
            "key_id":self.key_id,"receipt_id":str(uuid4()),
            "incident_id":incident_id,"component":component,"host":host,
            "action_id":action_id,"event_at":event_at,
            "operation":operation,"target":component,
            "status":status,"authorized":authorized,"evidence_ref":evidence_ref,
        }
        _validate(body)
        body["signature"]=base64.b64encode(self.__private_key.sign(_canonical(body))).decode("ascii")
        return body


def load_signer_from_file(path,*,role,key_id):
    """Trusted process only. Strict Linux 0600/owner, no symlinks, no env key bytes."""
    path=Path(path)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ReceiptV2Error("private_key_file_not_trusted")
    st=path.stat()
    if os.name != "nt" and (st.st_uid != os.geteuid() or st.st_mode & 0o077):
        raise ReceiptV2Error("private_key_permissions_unsafe")
    if st.st_size > 8192:
        raise ReceiptV2Error("private_key_file_oversized")
    try:
        key=load_pem_private_key(path.read_bytes(),password=None)
    except (ValueError, TypeError) as exc:
        raise ReceiptV2Error("private_key_file_invalid") from exc
    if not isinstance(key,Ed25519PrivateKey):
        raise ReceiptV2Error("unsupported_private_key")
    return Ed25519ReceiptSigner(role,key_id,key,expected_role=role)


class SignedReceiptSpool:
    """Untrusted bounded JSONL transport: signatures protect contents, not ACLs."""
    def __init__(self,path):
        self.path=Path(path)
        if self.path.is_symlink():
            raise ReceiptV2Error("spool_symlink_forbidden")

    def append(self,receipt):
        if self.path.is_symlink():
            raise ReceiptV2Error("spool_symlink_forbidden")
        payload=_canonical(receipt)
        if len(payload)>_MAX_RECEIPT or b"\n" in payload:
            raise ReceiptV2Error("spool_payload_invalid")
        self.path.parent.mkdir(parents=True,exist_ok=True)
        flags=os.O_APPEND|os.O_CREAT|os.O_WRONLY
        if hasattr(os,"O_NOFOLLOW"): flags |= os.O_NOFOLLOW
        fd=os.open(self.path,flags,0o600)
        try:
            if os.name != "nt":
                st=os.fstat(fd)
                if st.st_uid!=os.geteuid() or st.st_mode & 0o077:
                    raise ReceiptV2Error("spool_permissions_unsafe")
            blob=payload+b"\n"
            written=0
            while written<len(blob):
                count=os.write(fd,blob[written:])
                if count<=0:
                    raise ReceiptV2Error("incomplete_spool_write")
                written+=count
            os.fsync(fd)
        finally:
            os.close(fd)

    def read(self):
        if self.path.is_symlink():
            raise ReceiptV2Error("spool_symlink_forbidden")
        if not self.path.is_file(): return ()
        flags=os.O_RDONLY
        if hasattr(os,"O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd=os.open(self.path,flags)
        try:
            info=os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_size>262144:
                raise ReceiptV2Error("spool_untrusted_or_too_large")
            if os.name != "nt" and info.st_mode & 0o007:
                raise ReceiptV2Error("world_accessible_spool_forbidden")
            with os.fdopen(fd,"rb",closefd=False) as handle:
                raw=handle.read(262145)
            if len(raw)>262144:
                raise ReceiptV2Error("spool_too_large")
        finally:
            os.close(fd)
        try:
            if raw and not raw.endswith(b"\n"): raise ReceiptV2Error("spool_truncated")
            lines=raw.splitlines()
            if len(lines)>256: raise ReceiptV2Error("spool_limit")
            records=tuple(json.loads(x.decode("utf-8")) for x in lines)
            if any(type(r) is not dict for r in records):
                raise ReceiptV2Error("invalid_spool_record")
            return records
        except (UnicodeError,ValueError) as exc:
            raise ReceiptV2Error("invalid_spool_record") from exc


class Ed25519RecoveryVerifier:
    """Public-key-only verification; no secret material or action authority."""
    def __init__(self,public_keys,*,trusted_host,clock=None):
        if not _valid_id(trusted_host) or set(public_keys)!= {"executor","health_probe"}:
            raise ValueError("invalid_trust_policy")
        self.keys={}
        for role,ring in public_keys.items():
            if not isinstance(ring,dict) or not 1<=len(ring)<=3 or any(
                not _valid_id(name) or not isinstance(key,Ed25519PublicKey)
                for name,key in ring.items()
            ):
                raise ValueError("invalid_trust_roots")
            self.keys[role]=dict(ring)
        def fingerprints(ring):
            return {key.public_bytes(Encoding.Raw, PublicFormat.Raw)
                    for key in ring.values()}
        if fingerprints(self.keys["executor"]) & fingerprints(self.keys["health_probe"]):
            raise ValueError("shared_role_key_forbidden")
        self.host=trusted_host
        self.clock=clock or (lambda:datetime.now(timezone.utc))

    def _decode(self,signed):
        if type(signed) is not dict or set(signed)!=_FULL_FIELDS:
            raise ReceiptV2Error("invalid_signature_schema")
        if len(_canonical(signed))>_MAX_RECEIPT:
            raise ReceiptV2Error("oversized_signature")
        payload={name:signed[name] for name in _PAYLOAD_FIELDS}
        _validate(payload)
        public=self.keys[payload["issuer"]].get(payload["key_id"])
        if public is None: raise ReceiptV2Error("unknown_public_key")
        try:
            sig=base64.b64decode(signed["signature"],validate=True)
            if len(sig)!=64: raise ValueError("invalid_signature_length")
            public.verify(sig,_canonical(payload))
        except (InvalidSignature,ValueError,TypeError) as exc:
            raise ReceiptV2Error("signature_invalid") from exc
        return payload

    def verify_action(self,signed):
        info=self._decode(signed)
        if info["issuer"]!="executor" or info["host"]!=self.host:
            raise ReceiptV2Error("untrusted_action")
        return info

    def verify(self,incident,receipts):
        if (not isinstance(incident,dict) or incident.get("state")!="recovered"
                or incident.get("healthy_streak",0)<2 or
                not isinstance(receipts,(tuple,list)) or len(receipts)!=3):
            raise ReceiptV2Error("recovery_not_verified")
        a,b,c=tuple(self._decode(x) for x in receipts)
        if (tuple(x["issuer"] for x in (a,b,c))!=("executor","health_probe","health_probe")
            or {x["host"] for x in (a,b,c)}!={self.host}
            or {x["incident_id"] for x in (a,b,c)}!={incident["incident_id"]}
            or {x["component"] for x in (a,b,c)}!={incident["component"]}
            or len({x["action_id"] for x in (a,b,c)})!=1
            or len({x["receipt_id"] for x in (a,b,c)})!=3
            or b["evidence_ref"]==c["evidence_ref"]):
            raise ReceiptV2Error("receipt_correlation_invalid")
        observed=incident.get("recovery_evidence_refs",())
        if b["evidence_ref"] not in observed or c["evidence_ref"] not in observed:
            raise ReceiptV2Error("unobserved_health_proof")
        opened=_instant(incident["opened_at"])
        resolved=_instant(incident["resolved_at"])
        now=self.clock()
        if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ReceiptV2Error("verifier_clock_invalid")
        now=now.astimezone(timezone.utc)
        events=[_instant(x["event_at"]) for x in (a,b,c)]
        if not (opened<=events[0]<events[1]<events[2]<=resolved<=now
                and now-events[2]<=timedelta(hours=24)):
            raise ReceiptV2Error("receipt_order_or_age_invalid")
        return tuple("receipt:"+x["receipt_id"] for x in (a,b,c))


class ExecutorReceiptSink:
    """Called only by a typed executor *after* actual managed command success."""
    def __init__(self,signer,spool,memory,*,now=None):
        if signer.role!="executor": raise ValueError("executor_signer_required")
        self.signer=signer;self.spool=spool;self.memory=memory
        self.now=now or (lambda:datetime.now(timezone.utc))

    def __call__(self,capability,arguments,result):
        if capability not in ("start_service","restart_service"):
            return ()
        if not isinstance(result,dict) or result.get("status")!="success":
            return ()
        if not isinstance(arguments,dict): return ()
        host=arguments.get("host");component=arguments.get("service")
        if not _valid_id(host) or not _valid_id(component): return ()
        current=[i for i in self.memory.open_incidents()
                 if i["component"]==component and i["state"]=="open"]
        at=self.now()
        if not isinstance(at,datetime) or at.tzinfo is None: raise ReceiptV2Error("clock_invalid")
        emitted=[]
        for inc in current:
            if at.astimezone(timezone.utc) <= _instant(inc["opened_at"]):
                continue
            receipt=self.signer.sign(
                incident_id=inc["incident_id"],component=component,host=host,
                action_id=str(uuid4()),event_at=at.isoformat(),
                operation=capability,status="success",authorized=True,
                evidence_ref="execution:"+str(uuid4()))
            self.spool.append(receipt)
            emitted.append(receipt)
        return tuple(emitted)


class HealthReceiptSink:
    """Runs only in the independently privileged health-supervisor process."""
    def __init__(self,signer,action_spool,probe_spool,verifier,memory):
        if signer.role!="health_probe":
            raise ValueError("health_signer_required")
        self.signer=signer;self.actions=action_spool;self.probes=probe_spool
        self.verifier=verifier;self.memory=memory
        self.incident_publisher=None

    def publish_manifest(self, at):
        if self.incident_publisher is not None:
            self.incident_publisher.publish(self.memory,at)

    def annotate(self,snapshot:SupervisorSnapshot):
        if not isinstance(snapshot,SupervisorSnapshot):
            raise TypeError("snapshot_required")
        # Reading action journal grants no trust: verifier checks signatures.
        actions=self.actions.read()
        history=self.probes.read()
        changed=[]
        for comp in snapshot.components:
            if comp.state is not State.HEALTHY:
                changed.append(comp)
                continue
            open_inc=[x for x in self.memory.open_incidents()
                      if x["component"]==comp.component_id]
            for inc in open_inc:
                candidates=[]
                for signed in actions:
                    try: action=self.verifier.verify_action(signed)
                    except ReceiptV2Error: continue
                    if (action["incident_id"]==inc["incident_id"]
                        and action["component"]==comp.component_id
                        and action["host"]==comp.host
                        and _instant(action["event_at"])<_instant(snapshot.generated_at)):
                        candidates.append(action)
                if not candidates: continue
                action=max(candidates,key=lambda x:x["event_at"])
                for old in history:
                    try: valid=self.verifier._decode(old)
                    except ReceiptV2Error: continue
                    if (valid["issuer"]=="health_probe"
                        and valid["action_id"]==action["action_id"]
                        and valid["incident_id"]==inc["incident_id"]
                        and valid["event_at"]==snapshot.generated_at):
                        # Exactly one receipt per cycle.
                        break
                else:
                    proof_count=sum(1 for old in history
                        if type(old) is dict and old.get("action_id")==action["action_id"]
                        and old.get("incident_id")==inc["incident_id"])
                    if proof_count>=2: continue
                    ref="health:"+str(uuid4())
                    signed=self.signer.sign(
                        incident_id=inc["incident_id"],component=comp.component_id,
                        host=comp.host,action_id=action["action_id"],
                        event_at=snapshot.generated_at,operation="observe",
                        status="healthy",authorized=False,evidence_ref=ref)
                    self.probes.append(signed)
                    comp=replace(comp,evidence_refs=tuple((*comp.evidence_refs,ref)))
                    history=(*history,signed)
            changed.append(comp)
        return replace(snapshot,components=tuple(changed))


def learn_from_ed25519_recovery(memory,*,incident_id,cause,correction,receipts,verifier):
    if not isinstance(memory,FailureMemory) or not isinstance(verifier,Ed25519RecoveryVerifier):
        raise ReceiptV2Error("trusted_verifier_required")
    inc=memory.get_incident(incident_id)
    if inc is None: raise ReceiptV2Error("incident_unknown")
    refs=verifier.verify(inc,receipts)
    return memory.record_verified_lesson(
        incident_id=incident_id,cause=cause,correction=correction,
        verification_refs=refs,
        verifier=lambda refreshed,new_refs:
            new_refs==verifier.verify(refreshed,receipts))

def load_public_key_from_file(path):
    """Consumer loads only PEM public material, never a private signing key."""
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    path=Path(path)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ReceiptV2Error("public_key_file_not_trusted")
    metadata=path.stat()
    if metadata.st_size > 8192:
        raise ReceiptV2Error("public_key_file_oversized")
    if os.name=="posix" and (metadata.st_uid not in (0,os.geteuid())
                            or metadata.st_mode & 0o022):
        raise ReceiptV2Error("public_key_owner_or_mode_untrusted")
    try:
        key=load_pem_public_key(path.read_bytes())
    except (ValueError,TypeError) as exc:
        raise ReceiptV2Error("public_key_file_invalid") from exc
    if not isinstance(key,Ed25519PublicKey):
        raise ReceiptV2Error("unsupported_public_key")
    return key


def build_executor_receipt_sink(state_dir, memory, *, environ=None):
    """Explicit opt-in in control-service boundary, OFF by default."""
    env=os.environ if environ is None else environ
    if env.get("ATLAS_SENTRY_V2_EXECUTOR_ENABLED") != "1":
        return None
    signer=load_signer_from_file(
        env["ATLAS_SENTRY_V2_EXECUTOR_PRIVATE_KEY_FILE"],
        role="executor",key_id=env["ATLAS_SENTRY_V2_EXECUTOR_KEY_ID"],
    )
    if env.get("ATLAS_SENTRY_V2_TRANSPORT") == "unix":
        from .sentry_receipt_relay import UnixReceiptClient
        from .sentry_incident_manifest import ReadOnlyIncidentManifest
        # The executor must NOT open the supervisor's writable FailureMemory.
        memory=ReadOnlyIncidentManifest(
            Path(env["ATLAS_SENTRY_V2_INCIDENT_MANIFEST_FILE"]),
            load_public_key_from_file(env["ATLAS_SENTRY_V2_HEALTH_PUBLIC_KEY_FILE"]),
            key_id=env["ATLAS_SENTRY_V2_HEALTH_KEY_ID"],
            owner_uid=int(env["ATLAS_SENTRY_V2_HEALTH_UID"]),
            group_gid=int(env["ATLAS_SENTRY_V2_RELAY_GROUP_GID"]),
        )
        journal=UnixReceiptClient(
            Path(env["ATLAS_SENTRY_V2_RELAY_SOCKET"]),
            trusted_uid=int(env["ATLAS_SENTRY_V2_HEALTH_UID"]),
            trusted_gid=int(env["ATLAS_SENTRY_V2_RELAY_GROUP_GID"]),
        )
    else:
        if memory is None:
            raise ReceiptV2Error("sentry_memory_required")
        # P3 same-UID compatibility, not approved for cross-principal production.
        journal=SignedReceiptSpool(Path(state_dir)/"sentry-v2-actions.jsonl")
    return ExecutorReceiptSink(signer,journal,memory)


def build_health_receipt_sink(state_dir, memory, *, environ=None):
    """Independent health producer, only after explicit operator enablement."""
    env=os.environ if environ is None else environ
    if env.get("ATLAS_SENTRY_V2_HEALTH_ENABLED") != "1":
        return None
    if memory is None:
        raise ReceiptV2Error("sentry_memory_required")
    signer=load_signer_from_file(
        env["ATLAS_SENTRY_V2_HEALTH_PRIVATE_KEY_FILE"],
        role="health_probe",key_id=env["ATLAS_SENTRY_V2_HEALTH_KEY_ID"],
    )
    if env.get("ATLAS_SENTRY_V2_TRUST_KEYRING_FILE"):
        roots=load_public_key_ring(env["ATLAS_SENTRY_V2_TRUST_KEYRING_FILE"])
        expected=roots["health_probe"].get(signer.key_id)
        if expected is None or expected.public_bytes(Encoding.Raw,PublicFormat.Raw) != (
            signer.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
        ):
            raise ReceiptV2Error("health_signer_not_in_trust_bundle")
    else:
        action_public=load_public_key_from_file(
            env["ATLAS_SENTRY_V2_EXECUTOR_PUBLIC_KEY_FILE"]
        )
        roots={
            "executor":{env["ATLAS_SENTRY_V2_EXECUTOR_KEY_ID"]:action_public},
            "health_probe":{signer.key_id:signer.public_key()},
        }
    verifier=Ed25519RecoveryVerifier(
        roots,trusted_host="pentium",
    )
    if env.get("ATLAS_SENTRY_V2_TRANSPORT") == "unix":
        from .sentry_receipt_relay import RotatingReceiptJournal
        # Relay-owned action log must be read-only to the health principal.
        action_journal=RotatingReceiptJournal(
            Path(env["ATLAS_SENTRY_V2_RELAY_ACTION_JOURNAL"]))
        probe_journal=RotatingReceiptJournal(
            Path(env["ATLAS_SENTRY_V2_HEALTH_PROBE_JOURNAL"]))
    else:
        action_journal=SignedReceiptSpool(Path(state_dir)/"sentry-v2-actions.jsonl")
        probe_journal=SignedReceiptSpool(Path(state_dir)/"sentry-v2-probes.jsonl")
    sink=HealthReceiptSink(signer,action_journal,probe_journal,verifier,memory)
    if env.get("ATLAS_SENTRY_V2_TRANSPORT") == "unix":
        from .sentry_incident_manifest import SignedIncidentPublisher
        sink.incident_publisher=SignedIncidentPublisher(
            Path(env["ATLAS_SENTRY_V2_INCIDENT_MANIFEST_FILE"]),signer,
            group_gid=int(env["ATLAS_SENTRY_V2_RELAY_GROUP_GID"]),
        )
    return sink


def load_public_key_ring(path):
    """Root/health-owned 0600 JSON trust bundle, max 3 keys per issuer.

    Rotation: publish new+old public keys, restart relay and health, switch
    signing key, then revoke old keys after all pending evidence expires.
    Private key material is never accepted in this trust bundle.
    """
    path=Path(path)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ReceiptV2Error("trust_bundle_not_trusted")
    s=path.stat()
    if s.st_size>4096 or (os.name=="posix" and
        (s.st_uid!=os.geteuid() or s.st_mode&0o077)):
        raise ReceiptV2Error("trust_bundle_permissions_invalid")
    try:
        body=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,UnicodeError,ValueError) as exc:
        raise ReceiptV2Error("trust_bundle_invalid_json") from exc
    if (type(body) is not dict or set(body)!=
        {"version","executor","health_probe"} or body["version"]!=1):
        raise ReceiptV2Error("trust_bundle_schema_invalid")
    roots={}
    for role in ("executor","health_probe"):
        ring=body[role]
        if type(ring) is not dict or not 1<=len(ring)<=3:
            raise ReceiptV2Error("trust_bundle_role_invalid")
        roots[role]={}
        for key_id,filename in ring.items():
            if not _valid_id(key_id):
                raise ReceiptV2Error("trust_bundle_key_id_invalid")
            roots[role][key_id]=load_public_key_from_file(filename)
    # Verify role uniqueness with the same policy used at ingestion.
    Ed25519RecoveryVerifier(roots,trusted_host="pentium")
    return roots
