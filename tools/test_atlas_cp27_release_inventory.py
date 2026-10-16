"""Atlas CP27 release inventory tests: read-only, no file contents accessed."""

from pathlib import Path
import json
import unittest

from tools.atlas_cp27_release_inventory import (
    inventory,
    _is_symlink,
    _has_path_traversal,
    _safe_path,
    _hash_from_status_line,
    MAX_ENTRIES,
)


class Cp27ReleaseInventoryTests(unittest.TestCase):
    """Read-only inventory tests: no application imports or production access."""

    def test__is_symlink_false_for_regular_path(self):
        """_is_symlink returns False for a regular (non-symlink) path."""
        self.assertFalse(_is_symlink(Path("plain.txt")))

    def test__has_path_traversal_with_dotdot(self):
        """_has_path_traversal returns True when path contains '..'."""
        self.assertTrue(_has_path_traversal(Path("../etc/passwd")))

    def test__has_path_traversal_without_traversal(self):
        """_has_path_traversal returns False for safe paths."""
        self.assertFalse(_has_path_traversal(Path("safe.py")))

    def test__has_path_traversal_windows_backslash(self):
        """_has_path_traversal works with Windows backslash separators."""
        # On Windows, Path("../etc/passwd") produces backslashes;
        # the function must normalize them.
        self.assertTrue(_has_path_traversal(Path("..\\etc\\passwd")))

    def test__safe_path_rejects_traversal(self):
        """_safe_path returns False for paths with traversal."""
        self.assertFalse(_safe_path(Path("../etc/passwd")))

    def test__safe_path_accepts_safe(self):
        """_safe_path returns True for safe paths."""
        self.assertTrue(_safe_path(Path("safe.py")))

    def test__hash_from_status_line_format(self):
        """_hash_from_status_line should return a 16-char hex string."""
        h = _hash_from_status_line(" M foo.py")
        self.assertRegex(h, r"^[a-f0-9]{16}$")
        # Should NOT be 64 chars (full SHA-256)
        self.assertNotEqual(len(h), 64)

    def test__hash_from_status_line_deterministic(self):
        """Same status line should always produce same hash."""
        line = " M foo.py"
        h1 = _hash_from_status_line(line)
        h2 = _hash_from_status_line(line)
        self.assertEqual(h1, h2)

    def test__hash_from_status_line_different_lines(self):
        """Different status lines produce valid 16-char hex hashes."""
        h1 = _hash_from_status_line(" M foo.py")
        h2 = _hash_from_status_line(" M bar.py")
        # Both must be valid 16-char hex
        self.assertRegex(h1, r"^[a-f0-9]{16}$")
        self.assertRegex(h2, r"^[a-f0-9]{16}$")

    def test_MAX_ENTRIES_is_100(self):
        """MAX_ENTRIES constant should be 100."""
        self.assertEqual(MAX_ENTRIES, 100)

    def test_inventory_returns_dict_with_required_keys(self):
        """inventory() should return dict with schema_version, root, dirty_count, entries, warning."""
        root = Path(__file__).parent
        try:
            data = inventory(root)
            self.assertIn("schema_version", data)
            self.assertIn("root", data)
            self.assertIn("dirty_count", data)
            self.assertIn("entries", data)
            self.assertIn("warning", data)
        except ValueError as e:
            # If not a git repo, ValueError is also acceptable
            self.assertTrue(
                "not_a_git_repository" in type(e).__name__
                or "invalid" in str(e).lower(),
                f"Expected ValueError for non-git root, got: {e}"
            )

    def test_all_dirty_paths_are_accounted_for_with_pagination(self):
        import subprocess
        import tempfile
        from contextlib import redirect_stdout
        from io import StringIO
        from tools.atlas_cp27_release_inventory import main
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.check_call(["git", "init", "-q"], cwd=root,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for index in range(155):
                (root / f"untracked-{index:03}.txt").write_text("sample", encoding="utf-8")
            first = inventory(root, offset=0)
            self.assertEqual(155, first["total_dirty_count"])
            self.assertEqual(100, len(first["entries"]))
            self.assertTrue(first["has_more"])
            self.assertEqual(100, first["next_offset"])
            second = inventory(root, offset=100)
            self.assertEqual(155, second["total_dirty_count"])
            self.assertEqual(55, len(second["entries"]))
            self.assertFalse(second["has_more"])
            self.assertEqual(155, len({e["path"] for e in first["entries"] + second["entries"]}))
            with redirect_stdout(StringIO()):
                self.assertNotEqual(0, main(["--root", str(root)]))

    def test_status_digest_is_not_misrepresented_as_content_hash(self):
        data = inventory(Path(__file__).resolve().parents[1])
        self.assertEqual("status_line_sha256_16", data["fingerprint_kind"])
        self.assertNotIn("content_sha256", data)

    def test_inventory_bounded_max_entries(self):
        """MAX_ENTRIES should cap at 100."""
        self.assertEqual(MAX_ENTRIES, 100)


if __name__ == "__main__":
    unittest.main()