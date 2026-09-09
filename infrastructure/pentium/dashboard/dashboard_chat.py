from __future__ import annotations

import sys
from pathlib import Path

PARENT=Path(__file__).resolve().parents[1]
if str(PARENT) not in sys.path: sys.path.insert(0,str(PARENT))
from atlas.chat_inbox import ChatInbox

class DashboardChatGateway:
    def __init__(self,path:Path,*,max_message_chars:int=512):
        self.inbox=ChatInbox(Path(path),max_items=32,max_message_chars=max_message_chars)
    def submit(self,message:str,client_message_id:str)->dict:
        env=self.inbox.enqueue(message,client_message_id)
        return {'message_id':env.message_id,'stimulus_id':env.stimulus_id,'plan_pending':env.acked_at is None}
