"""CP-SENTRY-P5: deterministic, allowlisted, secret-free deployment payload.

Build/verify only. SHA-256 detects corruption, NOT a signature or a trust
anchor. A production installer must validate the commit/trusted release
separately and run under authorized system administration.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import zipfile
from pathlib import Path

ALLOWED = (
    "infrastructure/pentium/atlas/config_health_supervisor.json",
    "infrastructure/pentium/atlas/failure_memory.py",
    "infrastructure/pentium/atlas/health_probes.py",
    "infrastructure/pentium/atlas/health_supervisor.py",
    "infrastructure/pentium/atlas/health_supervisor_model.py",
    "infrastructure/pentium/atlas/health_supervisor_daemon.py",
    "infrastructure/pentium/atlas/multi_host_executor.py",
    "infrastructure/pentium/atlas/sentry_incident_manifest.py",
    "infrastructure/pentium/atlas/sentry_receipt_relay.py",
    "infrastructure/pentium/atlas/sentry_receipt_v2.py",
    "infrastructure/pentium/atlas/systemd-system/atlas-sentry-health.service",
    "infrastructure/pentium/atlas/systemd-system/atlas-sentry-receipt-relay.service",
    "infrastructure/pentium/atlas/systemd-system/atlas-sentry-receipt-relay.tmpfiles.conf",
    "infrastructure/pentium/atlas/systemd-system/relay.env.example",
    "tools/atlas_sentry_p5_preflight.py",
    "tools/atlas_sentry_v2_keys.py",
    "tools/atlas_sentry_v2_relay.py",
)
MANIFEST = "p5-payload-manifest.json"
LIMIT = 3 * 1024 * 1024


class BundleError(ValueError):
    pass


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _safe_content(repo,relative):
    path=repo/relative
    try:
        target=path.resolve(strict=True)
    except OSError as exc:
        raise BundleError("missing_release_file") from exc
    if not target.is_relative_to(repo.resolve()):
        raise BundleError("release_path_outside_repo")
    if path.is_symlink() or any(p.is_symlink() for p in path.parents if p!=repo.parent):
        raise BundleError("release_symlink_forbidden")
    info=target.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size>LIMIT:
        raise BundleError("release_file_unsafe")
    return target.read_bytes()


def create_bundle(repo, output):
    repo=Path(repo)
    output=Path(output)
    if not repo.is_dir() or output.exists() or output.is_symlink():
        raise BundleError("source_or_output_untrusted")
    if not output.parent.is_dir() or output.parent.is_symlink():
        raise BundleError("bundle_parent_untrusted")
    files={}
    for relative in ALLOWED:
        data=_safe_content(repo,relative)
        files[relative]={"sha256":_sha(data),"size":len(data)}
    manifest={
        "schema_version":1,
        "purpose":"atlas-sentry-p5-staging-only",
        "files":files,
    }
    manifest_bytes=json.dumps(manifest,sort_keys=True,
                              separators=(",",":")).encode("ascii")
    temp=output.with_name(output.name+".tmp."+str(os.getpid()))
    if temp.exists():
        raise BundleError("temporary_bundle_exists")
    try:
        with zipfile.ZipFile(temp,"x",compression=zipfile.ZIP_DEFLATED,
                             compresslevel=8) as archive:
            for relative in ALLOWED:
                info=zipfile.ZipInfo(relative,date_time=(1980,1,1,0,0,0))
                info.compress_type=zipfile.ZIP_DEFLATED
                info.external_attr=0o644<<16
                archive.writestr(info,_safe_content(repo,relative))
            info=zipfile.ZipInfo(MANIFEST,date_time=(1980,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o644<<16
            archive.writestr(info,manifest_bytes)
        verify_bundle(temp)
        os.replace(temp,output)
    finally:
        temp.unlink(missing_ok=True)
    return {"bundle_sha256":_sha(output.read_bytes()),"files":len(ALLOWED)}


def verify_bundle(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>LIMIT:
        raise BundleError("bundle_path_or_size_invalid")
    try:
        with zipfile.ZipFile(path,"r") as archive:
            infos=archive.infolist()
            names=[item.filename for item in infos]
            if (len(names)!=len(ALLOWED)+1 or len(names)!=len(set(names))
                    or set(names)!=set(ALLOWED)|{MANIFEST}):
                raise BundleError("bundle_allowlist_mismatch")
            if any(item.file_size>LIMIT or
                   item.filename.startswith("/") or ".." in Path(item.filename).parts
                   for item in infos):
                raise BundleError("bundle_entry_unsafe")
            with archive.open(MANIFEST) as src:
                manifest_bytes=src.read(100_000)
            body=json.loads(manifest_bytes)
            if (type(body) is not dict or set(body)!=
                {"schema_version","purpose","files"}
                or body["schema_version"]!=1
                or body["purpose"]!="atlas-sentry-p5-staging-only"
                or type(body["files"]) is not dict
                or set(body["files"])!=set(ALLOWED)):
                raise BundleError("bundle_manifest_invalid")
            total=0
            for relative in ALLOWED:
                expected=body["files"][relative]
                if type(expected) is not dict or set(expected)!={"sha256","size"}:
                    raise BundleError("bundle_metadata_invalid")
                with archive.open(relative) as source:
                    data=source.read(LIMIT+1)
                total+=len(data)
                if (total>LIMIT or len(data)!=expected["size"]
                    or _sha(data)!=expected["sha256"]):
                    raise BundleError("bundle_checksum_failed")
    except (OSError,zipfile.BadZipFile,UnicodeError,
            json.JSONDecodeError,KeyError,TypeError) as exc:
        raise BundleError("bundle_corrupted_or_unreadable") from exc
    return {"verified":True,"files":len(ALLOWED),"bundle_sha256":_sha(path.read_bytes())}


def main(argv=None):
    parser=argparse.ArgumentParser(description="Stage or verify P5 release inputs")
    action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--build",type=Path)
    action.add_argument("--verify",type=Path)
    parser.add_argument("--repo",type=Path,default=Path(__file__).resolve().parents[1])
    args=parser.parse_args(argv)
    try:
        result=create_bundle(args.repo,args.build) if args.build else verify_bundle(args.verify)
    except BundleError as exc:
        print(json.dumps({"ok":False,"reason":str(exc)},sort_keys=True))
        return 2
    print(json.dumps({"ok":True,**result},sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
