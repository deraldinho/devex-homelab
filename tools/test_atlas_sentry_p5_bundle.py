"""P5 reproducible allowlist bundle and adversarial checksum tests."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.atlas_sentry_p5_bundle import (
    ALLOWED, BundleError, MANIFEST, create_bundle, verify_bundle,
)


class P5BundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.repo=self.root/"repo"
        self.repo.mkdir()
        for name in ALLOWED:
            file=self.repo/name
            file.parent.mkdir(parents=True,exist_ok=True)
            file.write_bytes(("# P5 fixture: "+name+"\n").encode("utf-8"))
        self.out=self.root/"sentry-p5.zip"

    def test_expected_files_only_and_reproducible_bytes(self):
        first=create_bundle(self.repo,self.out)
        self.assertEqual(first["files"],len(ALLOWED))
        self.assertTrue(verify_bundle(self.out)["verified"])
        with zipfile.ZipFile(self.out) as archive:
            self.assertEqual(set(archive.namelist()),{*ALLOWED,MANIFEST})
            self.assertFalse(any(".env" in name and not name.endswith(".example")
                                 for name in archive.namelist()))
            manifest=json.loads(archive.read(MANIFEST))
            self.assertEqual(manifest["purpose"],"atlas-sentry-p5-staging-only")
        duplicate=self.root/"p5-second.zip"
        second=create_bundle(self.repo,duplicate)
        self.assertEqual(first["bundle_sha256"],second["bundle_sha256"])
        self.assertEqual(self.out.read_bytes(),duplicate.read_bytes())

    def test_rebuild_cannot_overwrite_existing_release(self):
        create_bundle(self.repo,self.out)
        original=self.out.read_bytes()
        with self.assertRaises(BundleError):
            create_bundle(self.repo,self.out)
        self.assertEqual(self.out.read_bytes(),original)

    def test_missing_source_fails_closed(self):
        (self.repo/ALLOWED[0]).unlink()
        with self.assertRaises(BundleError):
            create_bundle(self.repo,self.out)
        self.assertFalse(self.out.exists())

    def test_source_symlink_is_rejected(self):
        file=self.repo/ALLOWED[0]
        file.unlink()
        try:
            file.symlink_to(self.root/"outside.json")
        except OSError:
            self.skipTest("Windows does not allow unprivileged symlink creation")
        with self.assertRaises(BundleError):
            create_bundle(self.repo,self.out)

    def test_injected_extra_archive_member_is_rejected(self):
        create_bundle(self.repo,self.out)
        with zipfile.ZipFile(self.out,"a") as archive:
            archive.writestr("../../.ssh/id_ed25519","injected")
        with self.assertRaises(BundleError):
            verify_bundle(self.out)

    def test_manifest_digest_change_does_not_validate(self):
        create_bundle(self.repo,self.out)
        changed=self.root/"tampered.zip"
        with zipfile.ZipFile(self.out,"r") as src:
            entries={name:src.read(name) for name in src.namelist()}
        chosen=ALLOWED[1]
        entries[chosen]=b"tampered"
        with zipfile.ZipFile(changed,"w") as dest:
            for name,content in entries.items():
                dest.writestr(name,content)
        with self.assertRaises(BundleError):
            verify_bundle(changed)

    def test_truncated_archive_is_rejected(self):
        create_bundle(self.repo,self.out)
        self.out.write_bytes(self.out.read_bytes()[:57])
        with self.assertRaises(BundleError):
            verify_bundle(self.out)


if __name__=="__main__":
    unittest.main()
