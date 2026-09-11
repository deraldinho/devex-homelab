import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from infrastructure.pentium.atlas.action_executors import ActionExecutorRegistry
from infrastructure.pentium.atlas.action_plan import ActionType
from infrastructure.pentium.atlas.action_plan_store import ActionPlanStore
from infrastructure.pentium.atlas.action_planner import ActionPlanner
from infrastructure.pentium.atlas.action_policy import ActionPolicy
from infrastructure.pentium.atlas.capability_registry import atlas_capability_registry
from infrastructure.pentium.atlas.chat_inbox import ChatInbox
from infrastructure.pentium.atlas.cognitive_daemon import CognitiveDaemon
from infrastructure.pentium.atlas.policy_capabilities import PolicyCapabilities
from infrastructure.pentium.atlas.notification_policy import NotificationPolicy


class Loop:
    def __init__(self): self.calls=[]
    def processar(self,**kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(ativado=True,razao=None,motivo="interacao_humana",texto="O x99 esta sendo observado.",resumo="responder ao chat",confianca=.9,intencao=None,parametros_intencao=None,requer_confirmacao=False,solicitar_fala=False)

class Publisher:
    def publish_phase(self,*args,**kwargs): pass
    def publish(self,*args,**kwargs): pass


def snapshot():
    return SimpleNamespace(source_stimulus_id="obs-1",entity_id="x99",generated_at="2026-09-08T18:00:00+00:00",recent_changes=(),affective_state={})


class CognitiveChatRuntimeTests(unittest.TestCase):
    def test_chat_message_has_priority_and_reaches_action_plan(self):
        caps=PolicyCapabilities(atlas_capability_registry(),read_auto_allow=("get_host_status",),control_allow=())
        loop=Loop()
        with TemporaryDirectory() as tmp:
            root=Path(tmp); inbox=ChatInbox(root/"chat-inbox.json"); inbox.enqueue("Olhe para o x99 e me diga como ele esta","client-9")
            store=ActionPlanStore(root/"current.json",root/"history.jsonl")
            daemon=CognitiveDaemon(snapshot,lambda:{"mudancas_recentes":[]},loop,Publisher(),planner=ActionPlanner(),action_policy=ActionPolicy(caps),action_executor=ActionExecutorRegistry(),action_store=store,event_sink=lambda *args:None,chat_inbox=inbox)
            daemon.run_once(); plan=store.load_current()
            pending=inbox.pending_count()
        self.assertEqual("human_interaction",plan.trigger_kind)
        self.assertTrue(any(a.type is ActionType.CHAT_REPLY for a in plan.actions))
        self.assertTrue(any(a.type is ActionType.LOOK_AT for a in plan.actions))
        self.assertEqual(0,pending)
        self.assertTrue(loop.calls[0]["sinais_ativacao"]["interacao_humana"])

    def test_discord_route_reaches_human_stimulus_and_reply_event(self):
        caps=PolicyCapabilities(atlas_capability_registry(),read_auto_allow=("get_host_status",),control_allow=())
        loop=Loop(); events=[]
        with TemporaryDirectory() as tmp:
            root=Path(tmp); inbox=ChatInbox(root/"chat-inbox.json")
            inbox.enqueue("Como esta o core?","discord-99",channel="discord",actor_id="user-7",conversation_id="channel-9",reply_target="channel-9")
            store=ActionPlanStore(root/"current.json",root/"history.jsonl")
            daemon=CognitiveDaemon(snapshot,lambda:{"mudancas_recentes":[]},loop,Publisher(),planner=ActionPlanner(),action_policy=ActionPolicy(caps),action_executor=ActionExecutorRegistry(),action_store=store,event_sink=lambda kind,payload:events.append((kind,payload)),chat_inbox=inbox)
            daemon.run_once()
        human=loop.calls[0]["dados_contexto"]["mudancas_recentes"][-1]
        self.assertEqual("human.discord",human.source)
        reply=next(payload for kind,payload in events if kind=="chat_message" and payload.get("role")=="atlas")
        self.assertEqual("discord",reply["channel"])
        self.assertEqual("channel-9",reply["reply_target"])
        self.assertEqual("user-7",reply["actor_id"])

    def test_observation_notification_uses_same_cognitive_reply_pipeline(self):
        caps=PolicyCapabilities(atlas_capability_registry(),read_auto_allow=("get_host_status",),control_allow=())
        loop=Loop(); events=[]
        observed=SimpleNamespace(
            source_stimulus_id="gh-1",entity_id="repo:L2jToren",generated_at="2026-09-10T22:00:00+00:00",
            recent_changes=({"source":"github.deraldinho.L2jToren","kind":"status_changed","severity":"warning","novelty":1.0},),
            affective_state={"valencia":.4,"ativacao":.8,"estresse":.7,"confianca":.5,"engajamento":.8,"curiosidade":.6},
        )
        with TemporaryDirectory() as tmp:
            root=Path(tmp); store=ActionPlanStore(root/"current.json",root/"history.jsonl")
            daemon=CognitiveDaemon(
                lambda: observed,lambda:{"mudancas_recentes":list(observed.recent_changes)},loop,Publisher(),
                planner=ActionPlanner(),action_policy=ActionPolicy(caps),action_executor=ActionExecutorRegistry(),
                action_store=store,event_sink=lambda kind,payload:events.append((kind,payload)),
                notification_policy=NotificationPolicy(alert_channel_id="channel-9"),
            )
            daemon.run_once()
        reply=next(payload for kind,payload in events if kind=="chat_message" and payload.get("role")=="atlas")
        self.assertEqual("discord",reply["channel"])
        self.assertEqual("channel-9",reply["reply_target"])
        self.assertTrue(loop.calls[0]["sinais_ativacao"]["mudanca_estado"])

    def test_failed_chat_cycle_is_not_acked(self):
        class BrokenLoop:
            def processar(self,**kwargs): raise TimeoutError("slow")
        events=[]
        with TemporaryDirectory() as tmp:
            root=Path(tmp); inbox=ChatInbox(root/"chat-inbox.json"); inbox.enqueue("oi","c1")
            daemon=CognitiveDaemon(snapshot,lambda:{"mudancas_recentes":[]},BrokenLoop(),Publisher(),chat_inbox=inbox,event_sink=lambda kind,payload:events.append((kind,payload)))
            with self.assertRaises(TimeoutError): daemon.run_once()
            pending=inbox.pending_count(); attempts=inbox.list_items()[0].attempts
        self.assertEqual(1,pending)
        self.assertEqual(1,attempts)
        self.assertTrue(any(kind=="runtime_error" for kind,_ in events))
