import json,unittest
from urllib.error import HTTPError
from infrastructure.pentium.atlas.opencode_http_transport import OpenCodeHTTPTransport

class Reply:
    def __init__(self,value):self.value=value
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,n):return json.dumps(self.value).encode()
class TransportTests(unittest.TestCase):
    def transport(self,outputs,seen):
        def open_request(req,timeout):
            seen.append((req.full_url,req.get_header("Authorization")))
            value=outputs.pop(0)
            if isinstance(value,Exception):raise value
            return Reply(value)
        return OpenCodeHTTPTransport(base_url="http://127.0.0.1:49374",
            password="test-pass",directory="C:/safe",opener=open_request)
    def test_successful_session(self):
        seen=[]
        t=self.transport([{"data":{"id":"session1"}},{},{"data":{"outcome":"succeeded"}},
            {"data":[{"type":"assistant","content":[{"type":"text","text":"valid reply"}]}]}],seen)
        self.assertEqual(t(model="free",prompt="task",context="{}",max_tokens=10)["text"],"valid reply")
        self.assertEqual(len(seen),4)
        self.assertTrue(all(auth.startswith("Basic ") for _,auth in seen))
    def test_ambiguous_post_never_retried(self):
        seen=[]
        t=self.transport([{"data":{"id":"session1"}},TimeoutError()],seen)
        with self.assertRaises(TimeoutError):
            t(model="free",prompt="task",context="{}",max_tokens=10)
        self.assertEqual(len(seen),2)
    def test_rejects_non_loopback(self):
        with self.assertRaises(ValueError):
            OpenCodeHTTPTransport(base_url="https://remote.invalid",password="p",directory=".")
    def test_pre_dispatch_429(self):
        seen=[]
        t=self.transport([HTTPError("url",429,"limit",{},None)],seen)
        self.assertEqual(t(model="free",prompt="task",context="{}",max_tokens=10),
                         {"status":"unavailable","dispatched":False})
if __name__=="__main__":unittest.main()
