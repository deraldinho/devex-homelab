"""CP-SENTRY-P4: health-signed, read-only incident index for executor process.

An executor has *no writable access* to FailureMemory's SQLite. The independent
health owner exports only open incident identifiers, component and opened_at.
Each snapshot is Ed25519 signed, short-lived, and verified with the health
PUBLIC key. A source agent cannot add incidents or extend their lifetime.
"""
from __future__ import annotations

import base64
import json
import os
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .sentry_receipt_v2 import Ed25519ReceiptSigner, ReceiptV2Error

_MAX_INDEX=8192
_FIELDS=frozenset(("version","key_id","generated_at","host","incidents"))
_ENTRY=frozenset(("incident_id","component","opened_at"))


class ManifestSecurityError(ReceiptV2Error):
    """Reject missing, stale, unsigned or unauthorized service health projection."""


def _stamp(value):
    if not isinstance(value,str) or len(value)>48:
        raise ManifestSecurityError("index_timestamp_invalid")
    try:
        instant=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:
        raise ManifestSecurityError("index_timestamp_invalid") from exc
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ManifestSecurityError("index_timestamp_naive")
    return instant.astimezone(timezone.utc)


def _json(value):
    try:
        data=json.dumps(value,sort_keys=True,separators=(",",":"),
                        ensure_ascii=True,allow_nan=False).encode("ascii")
    except (ValueError,TypeError) as exc:
        raise ManifestSecurityError("index_json_invalid") from exc
    if len(data)>_MAX_INDEX:
        raise ManifestSecurityError("index_too_large")
    return data


def _check(payload):
    if type(payload) is not dict or set(payload)!=_FIELDS or payload["version"]!=1:
        raise ManifestSecurityError("index_schema_invalid")
    if payload["host"]!="pentium" or not isinstance(payload["key_id"],str):
        raise ManifestSecurityError("index_host_invalid")
    if not isinstance(payload["incidents"],list) or len(payload["incidents"])>32:
        raise ManifestSecurityError("index_incidents_invalid")
    _stamp(payload["generated_at"])
    seen=set()
    for entry in payload["incidents"]:
        if type(entry) is not dict or set(entry)!=_ENTRY or any(
            not isinstance(entry[k],str) or not 1<=len(entry[k])<=128
            for k in _ENTRY
        ):
            raise ManifestSecurityError("index_entry_invalid")
        _stamp(entry["opened_at"])
        if entry["incident_id"] in seen:
            raise ManifestSecurityError("index_incident_repeated")
        seen.add(entry["incident_id"])
    _json(payload)


class SignedIncidentPublisher:
    def __init__(self,path,signer,*,group_gid=None):
        self.path=Path(path)
        if not self.path.is_absolute() or self.path.is_symlink():
            raise ManifestSecurityError("index_absolute_path_required")
        if not isinstance(signer,Ed25519ReceiptSigner) or signer.role!="health_probe":
            raise ValueError("health_signer_required")
        if group_gid is not None and (type(group_gid) is not int or group_gid<0):
            raise ValueError("group_gid_invalid")
        self.signer=signer
        self.gid=group_gid

    def publish(self,memory,at):
        from .failure_memory import FailureMemory
        if not isinstance(memory,FailureMemory):
            raise ManifestSecurityError("source_memory_untrusted")
        records=memory.open_incidents()
        body={
            "version":1,"key_id":self.signer.key_id,"generated_at":at,
            "host":"pentium",
            "incidents":[{
                "incident_id":entry["incident_id"],
                "component":entry["component"],
                "opened_at":entry["opened_at"],
            } for entry in records],
        }
        _check(body)
        sig=self.signer.sign_blob(_json(body))
        envelope={**body,"signature":base64.b64encode(sig).decode("ascii")}
        data=_json(envelope)+b"\n"
        if self.path.parent.is_symlink() or not self.path.parent.is_dir():
            raise ManifestSecurityError("index_parent_not_trusted")
        if os.name=="posix":
            s=self.path.parent.stat()
            if s.st_uid!=os.geteuid() or s.st_mode & 0o022:
                raise ManifestSecurityError("index_parent_permissions")
        if self.path.is_symlink():
            raise ManifestSecurityError("index_symlink_denied")
        tmp=self.path.with_name(self.path.name+".tmp."+str(os.getpid()))
        fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        try:
            if os.name=="posix":
                if self.gid is not None:
                    os.fchown(fd,os.geteuid(),self.gid)
                    os.fchmod(fd,0o640)
            with os.fdopen(fd,"wb",closefd=False) as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            os.close(fd)
        try:
            os.replace(tmp,self.path)
        finally:
            tmp.unlink(missing_ok=True)


class ReadOnlyIncidentManifest:
    def __init__(self,path,public_key,*,key_id,owner_uid=None,group_gid=None,
                 clock=None,max_age_s=120):
        self.path=Path(path)
        if not self.path.is_absolute() or self.path.is_symlink():
            raise ManifestSecurityError("index_path_untrusted")
        if not isinstance(public_key,Ed25519PublicKey):
            raise ValueError("manifest_public_key_required")
        if type(key_id) is not str or not key_id:
            raise ValueError("key_id_required")
        if owner_uid is not None and (type(owner_uid) is not int or owner_uid<0):
            raise ValueError("manifest_owner_uid_invalid")
        self.public=public_key
        self.key_id=key_id
        self.owner_uid=owner_uid
        self.group_gid=group_gid
        self.clock=clock or (lambda:datetime.now(timezone.utc))
        if not 1<=max_age_s<=3600:
            raise ValueError("manifest_max_age_invalid")
        self.max_age=timedelta(seconds=max_age_s)

    def open_incidents(self):
        if self.path.is_symlink() or not self.path.is_file():
            raise ManifestSecurityError("manifest_not_available")
        flags=os.O_RDONLY
        if hasattr(os,"O_NOFOLLOW"):flags|=os.O_NOFOLLOW
        fd=os.open(self.path,flags)
        try:
            info=os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_size>_MAX_INDEX:
                raise ManifestSecurityError("manifest_file_untrusted")
            if os.name=="posix":
                if self.owner_uid is None or info.st_uid!=self.owner_uid:
                    raise ManifestSecurityError("manifest_owner_mismatch")
                if info.st_mode & 0o027 or (self.group_gid is not None and
                    (info.st_gid!=self.group_gid or not (info.st_mode&0o040))):
                    raise ManifestSecurityError("manifest_acl_untrusted")
            with os.fdopen(fd,"rb",closefd=False) as handle:
                raw=handle.read(_MAX_INDEX+1)
        finally:
            os.close(fd)
        if len(raw)>_MAX_INDEX or not raw.endswith(b"\n"):
            raise ManifestSecurityError("manifest_truncated")
        try:
            envelope=json.loads(raw.decode("utf-8"))
            signature=base64.b64decode(envelope.pop("signature"),validate=True)
        except (ValueError,TypeError,KeyError,UnicodeError) as exc:
            raise ManifestSecurityError("manifest_invalid_signature_field") from exc
        _check(envelope)
        if envelope["key_id"]!=self.key_id:
            raise ManifestSecurityError("manifest_key_not_allowed")
        try:
            self.public.verify(signature,_json(envelope))
        except (InvalidSignature,ValueError) as exc:
            raise ManifestSecurityError("manifest_signature_invalid") from exc
        now=self.clock()
        if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ManifestSecurityError("manifest_clock_invalid")
        age=now.astimezone(timezone.utc)-_stamp(envelope["generated_at"])
        if not -timedelta(seconds=30)<=age<=self.max_age:
            raise ManifestSecurityError("manifest_stale_or_future")
        return tuple({**entry,"state":"open"} for entry in envelope["incidents"])
