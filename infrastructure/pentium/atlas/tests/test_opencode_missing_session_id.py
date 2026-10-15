import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from infrastructure.pentium.atlas.opencode_http_transport import OpenCodeHTTPTransport
from infrastructure.pentium.atlas.tests.test_opencode_http_transport import Reply

class MissingSessionIdTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory=self.temp.name
        self.args={"model":"free","prompt":"task","context":"{}","max_tokens":10}
        self.job=hashlib.sha256(json.dumps(["free","task","{}",10],sort_keys=True).encode()).hexdigest()
        self.title="Atlas-Inference-"+self.job[:24]
        self.file=Path(self.temp.name)/"journal.json"
    def new(self,items,calls):
        def open_request(req,timeout):
            calls.append((req.full_url,req.get_method()))
            return Reply(items.pop(0))
        return OpenCodeHTTPTransport(base_url="http://127.0.0.1:49374",
            password="fake",directory=self.directory,opener=open_request,journal_path=self.file)
    def session(self,sid):
        return {"id":sid,"title":self.title,"agent":"plan",
            "model":{"providerID":"opencode","id":"free"},
            "location":{"directory":self.directory}}
    def test_unique_session_recovered_without_post(self):
        calls=[]
        responses=[{"data":[self.session("sid-1")]},
            {"data":{"outcome":"succeeded"}},
            {"data":[{"type":"assistant","content":[{"type":"text","text":"recovered"}]}]}]
        t=self.new(responses,calls)
        t.ledger.save({"state":"creating","job":self.job,"model":"free","title":self.title})
        self.assertEqual(t(**self.args)["text"],"recovered")
        self.assertTrue(all(method=="GET" for _,method in calls))
    def test_ambiguous_candidates_fail_closed(self):
        calls=[]
        t=self.new([{"data":[self.session("one"),self.session("two")]}],calls)
        t.ledger.save({"state":"creating","job":self.job,"model":"free","title":self.title})
        with self.assertRaises(TimeoutError):t(**self.args)
        self.assertEqual(len(calls),1)
    def test_no_session_found_fail_closed(self):
        calls=[]
        t=self.new([{"data":[]}],calls)
        t.ledger.save({"state":"creating","job":self.job,"model":"free","title":self.title})
        with self.assertRaises(TimeoutError):t(**self.args)
        self.assertEqual(len(calls),1)
if __name__=="__main__":unittest.main()
