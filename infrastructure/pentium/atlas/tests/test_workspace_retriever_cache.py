import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.workspace_index import WorkspaceIndex
from infrastructure.pentium.atlas.workspace_retriever import WorkspaceRetriever
from infrastructure.pentium.atlas.workspace_context_cache import WorkspaceContextCache

class WorkspaceRetrieverCacheTests(unittest.TestCase):
    def test_repeated_query_uses_persistent_cache_and_invalidates_on_index_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            index=WorkspaceIndex(root/'index.db')
            cache=WorkspaceContextCache(root/'cache.db',ttl_s=60,max_entries=8,clock=lambda:1.0)
            index.upsert('notes/a.md',title='a',digest='core runner',content='core runner ok',sha256='a')
            retriever=WorkspaceRetriever(index,cache=cache)
            first=retriever.retrieve('core')
            self.assertEqual(1,cache.count())
            second=retriever.retrieve('core')
            self.assertEqual(first,second)
            index.upsert('notes/b.md',title='b',digest='core novo',content='core novo',sha256='b')
            retriever.retrieve('core')
            self.assertEqual(2,cache.count())
            index.close(); cache.close()
