import json,sys
from pathlib import Path
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root.parent))
from atlas_agents_api import client
api=client()
for role in ('architecture','security','qa'):
    record=json.loads((root/'opencode-review'/role/'status.json').read_text())
    sid=record['attempts'][0]['session_id']
    session=api('/api/session/'+sid).get('data',{})
    msgs=api('/api/session/'+sid+'/message').get('data',[])
    assistants=[m for m in msgs if m.get('type')=='assistant']
    texts=[]
    tools=[]
    for m in assistants:
        for part in m.get('content',[]):
            if part.get('type')=='text' and part.get('text'):
                texts.append(part['text'])
            if part.get('type')=='tool':
                tools.append({'name':part.get('name') or part.get('tool'),'command':str(part.get('input') or part.get('args') or '')[:250]})
    report='\n\n'.join(texts)
    (root/'opencode-review'/role/'inspection-report.md').write_text(report,encoding='utf-8')
    print(json.dumps({'role':role,'outcome':session.get('outcome'),'cost':session.get('cost'),'text_chars':len(report),'text_preview':report[-1700:],'tool_counts':{name:sum(t['name']==name for t in tools) for name in set(t['name'] for t in tools)},'shell_calls':[t for t in tools if t['name']=='shell']},ensure_ascii=True),flush=True)
