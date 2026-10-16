"""CP-SENTRY-P4: POSIX peer-credential Unix relay + bounded signed journals.

Executor has only a writable Unix socket. The relay (running as an independent
service) verifies SO_PEERCRED and the executor's Ed25519 public key before
persisting a bounded receipt. Supervisor reads the relay-owned journal.
Neither the relay nor the verifier holds the executor private signing key.
"""
from __future__ import annotations

import json
import os
import socket
import stat
import struct
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .sentry_receipt_v2 import Ed25519RecoveryVerifier, ReceiptV2Error

MAX_FRAME=2048
MAX_AGE=timedelta(minutes=5)
RETAIN_FOR=timedelta(hours=48)


class RelaySecurityError(ReceiptV2Error):
    """Fail-closed transport rejection with no event contents in diagnostics."""


def _instant(value):
    if not isinstance(value,str) or len(value)>48:
        raise RelaySecurityError("receipt_time_invalid")
    try:
        stamp=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:
        raise RelaySecurityError("receipt_time_invalid") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise RelaySecurityError("receipt_time_untrusted")
    return stamp.astimezone(timezone.utc)


def _wire(value):
    if type(value) is not dict:
        raise RelaySecurityError("receipt_object_required")
    try:
        data=json.dumps(value,sort_keys=True,separators=(",",":"),
                        ensure_ascii=True,allow_nan=False).encode("ascii")
    except (TypeError,ValueError,OverflowError) as exc:
        raise RelaySecurityError("receipt_serialization_invalid") from exc
    if len(data)>MAX_FRAME or b"\n" in data:
        raise RelaySecurityError("receipt_frame_invalid")
    return data


def _trusted_file(path):
    if path.is_symlink():
        raise RelaySecurityError("symlink_receipt_journal_denied")
    if not path.exists():
        return
    state=path.stat()
    if not stat.S_ISREG(state.st_mode) or state.st_size>262144:
        raise RelaySecurityError("journal_not_regular_or_too_large")
    if os.name=="posix":
        if state.st_uid!=os.geteuid() or state.st_mode & 0o077:
            raise RelaySecurityError("journal_owner_or_permissions_invalid")


class RotatingReceiptJournal:
    """Bounded fail-closed log: preserves all fresh evidence, no silent discard.

    Archives are only pruned if every receipt is older than the retention
    window. If capacity is exhausted by fresh evidence, rejecting new
    attestations is safer than evicting proof of an incomplete recovery.
    Single writer per journal must be enforced by the service manager.
    """

    def __init__(self,path,*,max_records=64,max_archives=4):
        path=Path(path)
        if not path.is_absolute() or path.is_symlink():
            raise RelaySecurityError("journal_absolute_path_required")
        if type(max_records) is not int or not 1<=max_records<=256:
            raise ValueError("journal_records_limit_invalid")
        if type(max_archives) is not int or not 1<=max_archives<=12:
            raise ValueError("journal_archive_limit_invalid")
        self.path=path
        self.max_records=max_records
        self.max_archives=max_archives

    def _segment(self,index):
        return self.path if index==0 else self.path.with_name(
            self.path.name+"."+str(index))

    def _read_segment(self,path):
        _trusted_file(path)
        if not path.exists():
            return ()
        flags=os.O_RDONLY
        if hasattr(os,"O_NOFOLLOW"): flags |= os.O_NOFOLLOW
        try:
            fd=os.open(path,flags)
        except OSError as exc:
            raise RelaySecurityError("journal_unavailable") from exc
        try:
            s=os.fstat(fd)
            if not stat.S_ISREG(s.st_mode) or s.st_size>262144:
                raise RelaySecurityError("journal_unsafe")
            if os.name=="posix" and (s.st_uid!=os.geteuid() or s.st_mode&0o077):
                raise RelaySecurityError("journal_owner_or_permissions_invalid")
            with os.fdopen(fd,"rb",closefd=False) as h:
                body=h.read(262145)
        finally:
            os.close(fd)
        if len(body)>262144 or (body and not body.endswith(b"\n")):
            raise RelaySecurityError("journal_truncated")
        lines=body.splitlines()
        if len(lines)>self.max_records:
            raise RelaySecurityError("journal_record_limit")
        result=[]
        for line in lines:
            if len(line)>MAX_FRAME:
                raise RelaySecurityError("oversized_journal_record")
            try:
                val=json.loads(line.decode("utf-8"))
            except (UnicodeError,ValueError) as exc:
                raise RelaySecurityError("journal_corrupted") from exc
            if type(val) is not dict:
                raise RelaySecurityError("journal_record_invalid")
            _wire(val)
            if not isinstance(val.get("receipt_id"),str):
                raise RelaySecurityError("journal_id_invalid")
            _instant(val.get("event_at"))
            result.append(val)
        return tuple(result)

    def read(self):
        entries=[]
        for idx in range(self.max_archives,0,-1):
            entries.extend(self._read_segment(self._segment(idx)))
        entries.extend(self._read_segment(self.path))
        ids=[r["receipt_id"] for r in entries]
        if len(ids)!=len(set(ids)):
            raise RelaySecurityError("journal_duplicate_id")
        return tuple(entries)

    def append(self,receipt,*,now=None):
        data=_wire(receipt)
        if not isinstance(receipt.get("receipt_id"),str):
            raise RelaySecurityError("journal_id_invalid")
        at=now or datetime.now(timezone.utc)
        if not isinstance(at,datetime) or at.tzinfo is None or at.utcoffset() is None:
            raise RelaySecurityError("journal_clock_invalid")
        at=at.astimezone(timezone.utc)
        all_events=self.read()
        if any(r["receipt_id"]==receipt["receipt_id"] for r in all_events):
            previous=next(r for r in all_events if r["receipt_id"]==receipt["receipt_id"])
            if previous!=receipt:
                raise RelaySecurityError("journal_conflicting_replay")
            return "duplicate"

        # Prune only whole expired archive segments, never partial or live proofs.
        for idx in range(self.max_archives,0,-1):
            path=self._segment(idx)
            batch=self._read_segment(path)
            if batch and all(at-_instant(v["event_at"])>RETAIN_FOR for v in batch):
                path.unlink()
        # Validate again so any corrupt segment cannot be silently replaced.
        batches=[self._read_segment(self._segment(i))
                 for i in range(self.max_archives+1)]
        current=batches[0]
        if len(current)>=self.max_records:
            if batches[-1]:
                raise RelaySecurityError("journal_retention_capacity_exhausted")
            for idx in range(self.max_archives,0,-1):
                src=self._segment(idx-1)
                dst=self._segment(idx)
                if src.exists():
                    if dst.exists():
                        raise RelaySecurityError("journal_unexpected_destination")
                    os.replace(src,dst)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        if self.path.parent.is_symlink():
            raise RelaySecurityError("journal_parent_symlink_denied")
        if os.name=="posix":
            parent=self.path.parent.stat()
            if parent.st_uid!=os.geteuid() or parent.st_mode & 0o022:
                raise RelaySecurityError("journal_parent_owner_or_mode_invalid")
        flags=os.O_WRONLY|os.O_APPEND|os.O_CREAT
        if hasattr(os,"O_NOFOLLOW"):flags|=os.O_NOFOLLOW
        fd=os.open(self.path,flags,0o600)
        try:
            if os.name=="posix":
                s=os.fstat(fd)
                if s.st_uid!=os.geteuid() or s.st_mode&0o077:
                    raise RelaySecurityError("journal_permissions_invalid")
            blob=data+b"\n"
            # Each journal has exactly one configured process writer.
            written=0
            while written<len(blob):
                n=os.write(fd,blob[written:])
                if n<=0:raise RelaySecurityError("journal_partial_write")
                written+=n
            os.fsync(fd)
        finally:
            os.close(fd)
        return "stored"


class ReceiptRelay:
    """Read-only authorization policy: only trusted action signer + Unix UID."""
    def __init__(self,journal,verifier,*,allowed_uid,clock=None):
        if not isinstance(journal,RotatingReceiptJournal) or not isinstance(
            verifier,Ed25519RecoveryVerifier):
            raise TypeError("trusted_journal_and_verifier_required")
        if type(allowed_uid) is not int or allowed_uid<0:
            raise ValueError("allowed_uid_invalid")
        self.journal=journal;self.verifier=verifier
        self.allowed_uid=allowed_uid
        self.clock=clock or (lambda:datetime.now(timezone.utc))

    def accept(self,signed,*,peer_uid):
        if type(peer_uid) is not int or peer_uid!=self.allowed_uid:
            raise RelaySecurityError("peer_uid_denied")
        try:
            data=self.verifier.verify_action(signed)
        except ReceiptV2Error as exc:
            raise RelaySecurityError("untrusted_executor_signature") from exc
        now=self.clock()
        if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise RelaySecurityError("relay_clock_invalid")
        now=now.astimezone(timezone.utc)
        when=_instant(data["event_at"])
        if not -timedelta(seconds=30)<=now-when<=MAX_AGE:
            raise RelaySecurityError("relay_receipt_stale_or_future")
        try:
            return self.journal.append(signed,now=now)
        except (OSError,ReceiptV2Error) as exc:
            raise RelaySecurityError("journal_write_denied") from exc


class UnixReceiptClient:
    """Unprivileged producer sends a signed event; never writes receiver files."""
    def __init__(self,path,*,timeout_s=2.0,trusted_uid=None,trusted_gid=None):
        self.path=Path(path)
        if not self.path.is_absolute():
            raise ValueError("unix_relay_absolute_socket_required")
        if not 0.05<=float(timeout_s)<=10:
            raise ValueError("invalid_relay_timeout")
        for identity in (trusted_uid,trusted_gid):
            if identity is not None and (type(identity) is not int or identity<0):
                raise ValueError("socket_identity_invalid")
        self.timeout=float(timeout_s)
        self.trusted_uid=trusted_uid
        self.trusted_gid=trusted_gid

    def append(self,signed):
        if self.path.is_symlink():
            raise RelaySecurityError("socket_symlink_denied")
        if os.name=="posix":
            try:
                info=self.path.stat()
            except OSError as exc:
                raise RelaySecurityError("socket_unavailable") from exc
            if not stat.S_ISSOCK(info.st_mode) or info.st_mode & 0o007:
                raise RelaySecurityError("socket_type_or_mode_invalid")
            if self.trusted_uid is not None and info.st_uid!=self.trusted_uid:
                raise RelaySecurityError("socket_owner_mismatch")
            if self.trusted_gid is not None and info.st_gid!=self.trusted_gid:
                raise RelaySecurityError("socket_group_mismatch")
        frame=_wire(signed)+b"\n"
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
            sock.settimeout(self.timeout)
            sock.connect(str(self.path))
            sock.sendall(frame)
            sock.shutdown(socket.SHUT_WR)
            result=sock.recv(48)
        if result not in (b"STORED\n",b"DUPLICATE\n"):
            raise RelaySecurityError("relay_delivery_unconfirmed")
        return result==b"STORED\n"


class ReceiptRelayServer:
    """Linux-only socket server; kernel SO_PEERCRED is mandatory, no fallback."""
    def __init__(self,path,relay,*,group_id,socket_mode=0o660):
        path=Path(path)
        if os.name!="posix" or not hasattr(socket,"SO_PEERCRED"):
            raise RuntimeError("linux_peer_credentials_required")
        if (not path.is_absolute() or path.is_symlink()
                or not path.parent.is_dir() or path.parent.is_symlink()):
            raise RelaySecurityError("socket_path_not_trusted")
        parent=path.parent.stat()
        if parent.st_uid!=os.geteuid() or parent.st_mode&0o022:
            raise RelaySecurityError("socket_directory_owner_or_mode_invalid")
        if path.exists():
            raise RelaySecurityError("socket_already_exists")
        if type(group_id) is not int or group_id<0 or socket_mode not in (0o600,0o660):
            raise ValueError("relay_group_or_socket_mode_invalid")
        self.path=path;self.relay=relay;self.gid=group_id;self.mode=socket_mode
        self._sock=None
        self.accepted=0
        self.duplicates=0
        self.denied=0

    def __enter__(self):
        sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        try:
            sock.bind(str(self.path))
            os.chown(self.path,os.geteuid(),self.gid)
            os.chmod(self.path,self.mode)
            sock.listen(8)
            self._sock=sock
        except BaseException:
            sock.close()
            self.path.unlink(missing_ok=True)
            raise
        return self

    def __exit__(self,*_):
        if self._sock:
            self._sock.close()
            self._sock=None
        self.path.unlink(missing_ok=True)

    def publish_status(self,path):
        """Persist counts only. No receipt IDs, credentials or user prompts."""
        dest=Path(path)
        if not dest.is_absolute() or dest.is_symlink() or not dest.parent.is_dir():
            raise RelaySecurityError("relay_status_path_invalid")
        if os.name=="posix":
            root=dest.parent.stat()
            if root.st_uid!=os.geteuid() or root.st_mode&0o022:
                raise RelaySecurityError("relay_status_directory_untrusted")
        payload=json.dumps({
            "schema_version":1,
            "accepted":self.accepted,
            "duplicates":self.duplicates,
            "denied":self.denied,
        },sort_keys=True,separators=(",",":")).encode("utf-8")+b"\n"
        tmp=dest.with_name(dest.name+".tmp."+str(os.getpid()))
        flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL
        if hasattr(os,"O_NOFOLLOW"): flags|=os.O_NOFOLLOW
        fd=os.open(tmp,flags,0o600)
        try:
            os.write(fd,payload)
            os.fsync(fd)
        finally:
            os.close(fd)
        try:
            if dest.is_symlink():
                raise RelaySecurityError("relay_status_symlink_forbidden")
            os.replace(tmp,dest)
        finally:
            tmp.unlink(missing_ok=True)

    def serve_one(self):
        if self._sock is None:
            raise RuntimeError("socket_not_started")
        client,_=self._sock.accept()
        with client:
            client.settimeout(2.0)
            cred=client.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12)
            _,uid,_=struct.unpack("3i",cred)
            try:
                raw=bytearray()
                while len(raw)<=MAX_FRAME:
                    chunk=client.recv(min(512,MAX_FRAME+1-len(raw)))
                    if not chunk:break
                    raw.extend(chunk)
                    if b"\n" in chunk:break
                if (len(raw)>MAX_FRAME or not raw.endswith(b"\n")
                        or raw.count(b"\n")!=1):
                    raise RelaySecurityError("invalid_socket_frame")
                try:
                    payload=json.loads(raw[:-1].decode("utf-8"))
                except (UnicodeError,ValueError) as exc:
                    raise RelaySecurityError("invalid_socket_json") from exc
                verdict=self.relay.accept(payload,peer_uid=uid)
                if verdict=="duplicate":
                    self.duplicates+=1
                    response=b"DUPLICATE\n"
                else:
                    self.accepted+=1
                    response=b"STORED\n"
            except (ReceiptV2Error,OSError):
                self.denied+=1
                response=b"DENY\n"
            try:
                client.sendall(response)
            except OSError:
                pass
            return response==b"STORED\n"
