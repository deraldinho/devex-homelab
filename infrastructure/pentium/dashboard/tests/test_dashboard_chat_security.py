import http.client, json, sys, threading, unittest
from pathlib import Path
from tempfile import TemporaryDirectory
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import atlas_dashboard, dashboard_collectors

class FakeCollectors:
    @staticmethod
    def collect_status(config): return {}
    @staticmethod
    def collect_events(config): return []

class DashboardChatSecurityTests(unittest.TestCase):
    def test_sse_filters_sensitive_payload_keys(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/'events.jsonl'
            path.write_text(json.dumps({'id':1,'type':'runtime_error','payload':{'error':'x','secret':'do-not-expose','token':'abc'}})+'\n',encoding='utf-8')
            server=atlas_dashboard.build_server({'bind_host':'127.0.0.1','bind_port':0,'dashboard_events_path':str(path)},collectors=FakeCollectors)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                host,port=server.server_address;conn=http.client.HTTPConnection(host,port,timeout=2);conn.request('GET','/api/stream');res=conn.getresponse();body=res.read();conn.close()
            finally:
                server.shutdown();server.server_close();thread.join(timeout=2)
            self.assertEqual(200,res.status);self.assertNotIn(b'do-not-expose',body);self.assertNotIn(b'abc',body);self.assertIn(b'"error":"x"',body)

    def test_malformed_cognitive_runtime_degrades(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);runtime=root/'runtime.json';runtime.write_text('{bad',encoding='utf-8')
            cfg={**dashboard_collectors.default_config(),'cognitive_runtime_path':str(runtime)}
            self.assertEqual('unavailable',dashboard_collectors.collect_cognitive_runtime(cfg)['status'])

if __name__=='__main__':unittest.main()
