import tempfile,unittest
from pathlib import Path
from infrastructure.pentium.atlas.opencode_http_transport import OpenCodeHTTPTransport
from infrastructure.pentium.atlas.tests.test_opencode_http_transport import Reply

class SessionRecoveryTests(unittest.TestCase):
    def test_timeout_then_reconcile_without_repost(self):
        with tempfile.TemporaryDirectory() as folder:
            sent=[]
            outputs=[{"data":{"id":"s1"}},{},{"data":{"outcome":"running"}}]
            def first(req,timeout):
                sent.append((req.full_url,req.get_method()))
                return Reply(outputs.pop(0))
            ledger=Path(folder)/"journal.json"
            t=OpenCodeHTTPTransport(base_url="http://127.0.0.1:49374",password="fake",
                directory=folder,opener=first,journal_path=ledger)
            args={"model":"free","prompt":"task","context":"{}","max_tokens":10}
            with self.assertRaises(TimeoutError): t(**args)
            self.assertEqual(len(sent),3)
            self.assertEqual(t.ledger.read()["session_id"],"s1")
            second_calls=[]
            results=[{"data":{"outcome":"succeeded"}},
                     {"data":[{"type":"assistant","content":[{"type":"text","text":"recovered"}]}]}]
            def second(req,timeout):
                second_calls.append((req.full_url,req.get_method()))
                return Reply(results.pop(0))
            t2=OpenCodeHTTPTransport(base_url="http://127.0.0.1:49374",password="fake",
                directory=folder,opener=second,journal_path=ledger)
            self.assertEqual(t2(**args)["text"],"recovered")
            self.assertTrue(all(method=="GET" for _,method in second_calls))
            self.assertEqual(t2(**args)["text"],"recovered")
    def test_creating_state_blocks_second_dispatch(self):
        with tempfile.TemporaryDirectory() as folder:
            t=OpenCodeHTTPTransport(base_url="http://127.0.0.1:49374",password="fake",
                directory=folder,journal_path=Path(folder)/"j.json")
            t.ledger.save({"state":"creating","job":"other"})
            with self.assertRaises(TimeoutError):
                t(model="free",prompt="task",context="{}",max_tokens=10)
if __name__=="__main__":unittest.main()
