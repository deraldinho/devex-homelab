"""Offline one-time CP-SENTRY-P3 key provisioner. NEVER generates keys on import.

Run as the dedicated service account, with a private parent directory, separately
on the executor and on the health supervisor. No keys are printed or checked in.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, PrivateFormat, PublicFormat, NoEncryption,
)


def _target(path):
    path=Path(path)
    if not path.is_absolute() or path.exists() or path.is_symlink():
        raise ValueError("target_must_be_new_absolute_file")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise ValueError("trusted_parent_directory_required")
    if os.name != "nt":
        stat=path.parent.stat()
        if stat.st_uid != os.geteuid() or stat.st_mode & 0o022:
            raise ValueError("parent_directory_writable_by_other_users")
    return path


def _new_file(path,body,mode):
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL
    if hasattr(os,"O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd=os.open(str(path),flags,mode)
    try:
        if os.name != "nt":
            os.fchmod(fd,mode)
        written=0
        while written<len(body):
            n=os.write(fd,body[written:])
            if n<=0:
                raise OSError("incomplete_key_write")
            written+=n
        os.fsync(fd)
    finally:
        os.close(fd)


def provision_keypair(private_path,public_path):
    private=_target(private_path)
    public=_target(public_path)
    if private==public:
        raise ValueError("key_paths_must_be_distinct")
    private_key=Ed25519PrivateKey.generate()
    secret=private_key.private_bytes(
        Encoding.PEM,PrivateFormat.PKCS8,NoEncryption())
    public_bytes=private_key.public_key().public_bytes(
        Encoding.PEM,PublicFormat.SubjectPublicKeyInfo)
    created_private=False
    try:
        _new_file(private,secret,0o600)
        created_private=True
        _new_file(public,public_bytes,0o644)
    except Exception:
        if created_private:
            private.unlink(missing_ok=True)
        raise
    return (private,public)


def main():
    parser=argparse.ArgumentParser(description="Generate distinct Ed25519 producer keys OFFLINE")
    parser.add_argument("--private",type=Path,required=True)
    parser.add_argument("--public",type=Path,required=True)
    args=parser.parse_args()
    provision_keypair(args.private,args.public)
    print("SENTRY_V2_KEYPAIR_CREATED (contents omitted)")


if __name__=="__main__":
    main()
