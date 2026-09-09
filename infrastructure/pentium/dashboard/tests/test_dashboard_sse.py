import http.client
import json
import threading
import unittest
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dashboard_event_store import DashboardEventStore
import atlas_dashboard

class FakeCollectors:
    @staticmethod
    def collect_status(config): return {}
    @staticmethod
    def collect_events(config): return []

class DashboardSseTests(unittest.TestCase):
    def test_store_replays_after_id_and_bounds_history(self):
        with TemporaryDirectory() as tmp:
            store=DashboardEventStore(Path(tmp)/'events.jsonl',max_events=3,max_bytes=4096)
            for i in range(5): store.append('action_status',{'n':i})
            self.assertEqual([4,5],[e['id'] for e in store.after(3)])
            self.assertLessEqual(len((Path(tmp)/'events.jsonl').read_text().splitlines()),3)

    def test_sse_replays_last_event_id(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/'events.jsonl'; store=DashboardEventStore(path)
            store.append('plan_created',{'plan_id':'p1'}); store.append('action_status',{'action_id':'a1'})
            server=atlas_dashboard.build_server({'bind_host':'127.0.0.1','bind_port':0,'dashboard_events_path':str(path)},collectors=FakeCollectors)
            thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
            try:
                host,port=server.server_address; conn=http.client.HTTPConnection(host,port,timeout=2)
                conn.request('GET','/api/stream',headers={'Last-Event-ID':'1'}); res=conn.getresponse(); body=res.read(); headers=dict(res.getheaders()); conn.close()
                self.assertEqual(200,res.status); self.assertIn('text/event-stream',headers['Content-Type']); self.assertIn(b'id: 2',body); self.assertNotIn(b'id: 1\n',body)
            finally:
                server.shutdown(); server.server_close(); thread.join(timeout=2)

if __name__=='__main__': unittest.main()
