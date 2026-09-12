import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.workspace_context_cache import WorkspaceContextCache


class WorkspaceContextCacheTests(unittest.TestCase):
    def test_hit_e_miss_por_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = WorkspaceContextCache(Path(tmp) / "cache.sqlite3", ttl_s=300, max_entries=8, clock=lambda: 10.0)
            self.assertIsNone(cache.get(content_hash="a", query="q", intent="i", policy_version="v1"))
            cache.put(content_hash="a", query="q", intent="i", policy_version="v1", value={"x": 1})
            self.assertEqual({"x": 1}, cache.get(content_hash="a", query="q", intent="i", policy_version="v1"))
            cache.close()

    def test_mudanca_hash_ou_policy_invalida(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = WorkspaceContextCache(Path(tmp) / "cache.sqlite3", ttl_s=300, max_entries=8, clock=lambda: 10.0)
            cache.put(content_hash="a", query="q", intent="i", policy_version="v1", value={"x": 1})
            self.assertIsNone(cache.get(content_hash="b", query="q", intent="i", policy_version="v1"))
            self.assertIsNone(cache.get(content_hash="a", query="q", intent="i", policy_version="v2"))
            cache.close()

    def test_ttl_expira(self):
        now = [10.0]
        with tempfile.TemporaryDirectory() as tmp:
            cache = WorkspaceContextCache(Path(tmp) / "cache.sqlite3", ttl_s=5, max_entries=8, clock=lambda: now[0])
            cache.put(content_hash="a", query="q", intent="i", policy_version="v1", value={"x": 1})
            now[0] = 16.0
            self.assertIsNone(cache.get(content_hash="a", query="q", intent="i", policy_version="v1"))
            cache.close()

    def test_cache_sobrevive_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cache.sqlite3"
            first = WorkspaceContextCache(path, ttl_s=300, max_entries=8, clock=lambda: 10.0)
            first.put(content_hash="a", query="q", intent="i", policy_version="v1", value={"x": 1})
            first.close()
            second = WorkspaceContextCache(path, ttl_s=300, max_entries=8, clock=lambda: 20.0)
            self.assertEqual({"x": 1}, second.get(content_hash="a", query="q", intent="i", policy_version="v1"))
            second.close()

    def test_max_entries_remove_mais_antiga(self):
        now = [1.0]
        with tempfile.TemporaryDirectory() as tmp:
            cache = WorkspaceContextCache(Path(tmp) / "cache.sqlite3", ttl_s=300, max_entries=2, clock=lambda: now[0])
            for idx in range(3):
                now[0] += 1
                cache.put(content_hash=str(idx), query="q", intent="i", policy_version="v1", value={"i": idx})
            self.assertIsNone(cache.get(content_hash="0", query="q", intent="i", policy_version="v1"))
            self.assertEqual(2, cache.count())
            cache.close()


if __name__ == "__main__":
    unittest.main()
