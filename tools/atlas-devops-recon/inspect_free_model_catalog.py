"""Read-only provider catalog inspection; no API calls to models."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from atlas_agents_api import client
r=client()("/api/provider")
def walk(value):
 if isinstance(value,dict):
  for k,v in value.items():
   if isinstance(k,str) and ('nemotron' in k.lower() or 'ultra' in k.lower() or 'free' in k.lower()):
    print(json.dumps({"key":k,"data":str(v)[:210]},ensure_ascii=True))
   walk(v)
 elif isinstance(value,list):
  for x in value:walk(x)
walk(r)
