import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.workspace_certification import WorkspaceCertification


class WorkspaceCertificationTests(unittest.TestCase):
    def test_certification_passes_all_fail_closed_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            report=WorkspaceCertification(Path(tmp)).run(expected_sha='a'*40)
        self.assertTrue(report['passed'])
        self.assertEqual('a'*40,report['expected_sha'])
        required={
            'traversal_blocked','internal_area_blocked','executable_blocked',
            'quota_blocked','purge_not_autonomous','no_generic_shell_or_filesystem',
            'human_priority_preserved','incident_priority_preserved',
        }
        self.assertEqual(required,set(report['checks']))
        self.assertTrue(all(report['checks'].values()))

    def test_invalid_sha_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                WorkspaceCertification(Path(tmp)).run(expected_sha='bad')

if __name__=='__main__': unittest.main()
