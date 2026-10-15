import tempfile
import json
import unittest
from pathlib import Path
from infrastructure.pentium.atlas.atlas_adaptive_discord_report import report,compose
class NativeDiscordReportTests(unittest.TestCase):
 def test_hourly_and_change_deduplication(self):
  with tempfile.TemporaryDirectory() as folder:
   q=Path(folder)/"queue.jsonl";state=Path(folder)/"state.json"
   base={"candidates":12,"catalog_nous":7,"catalog_nvidia":80,"changed":False}
   self.assertTrue(report(base,queue_path=q,state_path=state,now=10000))
   self.assertFalse(report(base,queue_path=q,state_path=state,now=10100))
   self.assertTrue(report(base,queue_path=q,state_path=state,now=13610))
   changed={**base,"catalog_nvidia":79}
   self.assertTrue(report(changed,queue_path=q,state_path=state,now=13800))
   rows=[json.loads(line) for line in q.read_text().splitlines()]
   self.assertEqual(len(rows),3)
   self.assertTrue(all(row["capability"]=="discord_send_alert" for row in rows))
   self.assertTrue(all(row["arguments"]["channel"]=="" for row in rows))
 def test_no_secret_values_in_reporting(self):
  msg,_=compose({"candidates":12,"catalog_nous":7,"catalog_nvidia":80,"changed":True},now=10000)
  self.assertNotIn("nvapi",msg)
  self.assertIn("Atlas",msg)
 def test_invalid_result_rejected(self):
  with self.assertRaises(ValueError):compose({"candidates":2},now=10000)
if __name__=="__main__":unittest.main()
