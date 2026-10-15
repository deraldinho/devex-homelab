import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from infrastructure.pentium.atlas.opencode_session_pool import OpenCodeSessionPool

class PoolTests(unittest.TestCase):
    def test_separate_journals_and_duplicate_reuse(self):
        with tempfile.TemporaryDirectory() as folder:
            pool=OpenCodeSessionPool(base_url="http://127.0.0.1:49374",
                password="test",directory=folder,journal_dir=folder,
                authorized_free_models={"free"})
            journals=[]
            def factory(**kwargs):
                journals.append(Path(kwargs["journal_path"]))
                return lambda **job:{"status":"ok","text":"mocked"}
            with patch("infrastructure.pentium.atlas.opencode_session_pool.OpenCodeHTTPTransport",side_effect=factory):
                pool(model="free",prompt="A",context="{}",max_tokens=10)
                pool(model="free",prompt="B",context="{}",max_tokens=10)
                pool(model="free",prompt="A",context="{}",max_tokens=10)
            self.assertNotEqual(journals[0],journals[1])
            self.assertEqual(journals[0],journals[2])
    def test_unauthorized_model_rejected_before_http(self):
        with tempfile.TemporaryDirectory() as folder:
            pool=OpenCodeSessionPool(base_url="http://127.0.0.1:49374",
                password="test",directory=folder,journal_dir=folder,
                authorized_free_models={"free"})
            with self.assertRaises(ValueError):
                pool(model="paid",prompt="A",context="{}",max_tokens=10)
if __name__=="__main__":unittest.main()
