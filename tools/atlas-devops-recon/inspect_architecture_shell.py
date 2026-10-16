import json,sys
from pathlib import Path
r=Path(__file__).resolve().parent
sys.path.insert(0,str(r.parent))
from atlas_agents_api import client
api=client()
sid='ses_ebff53722ffegvvgE0NlEQbwm8'
messages=api('/api/session/'+sid+'/message').get('data',[])
for msg in messages:
 if msg.get('type')!='assistant':continue
 for part in msg.get('content',[]):
  if part.get('type')=='tool' and (part.get('name') or part.get('tool'))=='shell':
   print(json.dumps({'keys':sorted(part.keys()),'part':str(part)[:2600]},ensure_ascii=True))
