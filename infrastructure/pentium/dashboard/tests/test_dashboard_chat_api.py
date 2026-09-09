import http.client, json, sys, threading, unittest
from pathlib import Path
from tempfile import TemporaryDirectory
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
import atlas_dashboard

class FakeCollectors:
    @staticmethod
    def collect_status(config): return {}
    @staticmethod
    def collect_events(config): return []

class DashboardChatApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory(); path=Path(self.tmp.name)/'chat-inbox.json'
        self.server=atlas_dashboard.build_server({'bind_host':'127.0.0.1','bind_port':0,'chat_inbox_path':str(path)},collectors=FakeCollectors)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True); self.thread.start(); self.host,self.port=self.server.server_address
    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=2); self.tmp.cleanup()
    def post(self,payload,path='/api/chat',content_type='application/json'):
        body=json.dumps(payload).encode(); conn=http.client.HTTPConnection(self.host,self.port,timeout=2)
        conn.request('POST',path,body=body,headers={'Content-Type':content_type,'Content-Length':str(len(body))}); res=conn.getresponse(); data=res.read(); conn.close(); return res.status,data
    def test_chat_is_202_and_idempotent(self):
        status,body=self.post({'message':'Oi Atlas','client_message_id':'c1'}); first=json.loads(body)
        status2,body2=self.post({'message':'Oi Atlas','client_message_id':'c1'}); second=json.loads(body2)
        self.assertEqual(202,status); self.assertEqual(202,status2); self.assertEqual(first['message_id'],second['message_id']); self.assertTrue(first['plan_pending']); self.assertEqual(first['stimulus_id'],second['stimulus_id'])
    def test_bounds_content_type_and_other_posts(self):
        self.assertEqual(413,self.post({'message':'x'*513,'client_message_id':'c2'})[0])
        self.assertEqual(415,self.post({'message':'oi','client_message_id':'c3'},content_type='text/plain')[0])
        self.assertEqual(405,self.post({'message':'oi','client_message_id':'c4'},path='/api/status')[0])

if __name__=='__main__': unittest.main()
