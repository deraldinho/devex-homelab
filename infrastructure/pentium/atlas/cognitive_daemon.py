from __future__ import annotations

import json
import os
import signal
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from .capability_registry import atlas_capability_registry
from .action_executors import ActionExecutorRegistry
from .autonomy_executor import SafeLocalCapabilityExecutor
from .action_plan import ActionStatus, ActionType
from .action_plan_store import ActionPlanStore
from .action_planner import ActionPlanner
from .action_policy import ActionPolicy
from .affective_interaction_ipc import InteractionDatagramClient
from .cognitive_cache import CognitiveCache
from .cognitive_observability import CognitiveObservablePublisher, CognitiveActionEventPublisher
from .config_cache import load_cache_config
from .config_memory import load_memory_config
from .config_hermes import load_hermes_config
from .configuracao_cognitiva import carregar_configuracao_cognitiva
from .contexto_cognitivo import ContextoCognitivoBuilder
from .cognitive_observation_projection import load_cognitive_observation_snapshot
from .human_context import HumanContextProvider
from .human_interaction import build_human_stimulus
from .chat_inbox import ChatInbox
from .hermes_adapter import HermesAdapter
from .llm_gateway import LLMGateway
from .memory_retriever import MemoryRetriever
from .memory_store import MemoryStore
from .modelo_visual_atlas import EstadoInteracaoVisual, EstadoVisualAtlas, ModoVisual, ExpressaoVisual
from .visual_state_publisher import VisualStatePublisher
from .policy_capabilities import PolicyCapabilities
from .politica_ativacao_cognitiva import ActivationPolicy
from .reaction_loop_cognitivo import ReactionLoopCognitivo
from .reasoning_policy import ReasoningPolicy
from .notification_policy import load_notification_policy

ROOT=Path(__file__).resolve().parent
AGENT_ROOT=Path.home()/"pentium-agent"
STATE_DIR=AGENT_ROOT/"atlas"/"runtime"


def _utc_now()->str:
    return datetime.now(timezone.utc).isoformat()


def read_visual_state(path: Path) -> EstadoVisualAtlas:
    path = Path(path)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return EstadoVisualAtlas(
                modo=data.get("modo", ModoVisual.OCIOSO),
                expressao=data.get("expressao", ExpressaoVisual.SERENO),
                intensidade_expressao=float(data.get("intensidade_expressao", 0.5)),
                foco_visual=str(data.get("foco_visual", "neutro")),
                direcao_olhar=str(data.get("direcao_olhar", "centro")),
                gesto_atual=str(data.get("gesto_atual", "NENHUM")),
                velocidade_movimento=float(data.get("velocidade_movimento", 0.5)),
                intensidade_movimento=float(data.get("intensidade_movimento", 0.5)),
                falando=bool(data.get("falando", False)),
                ouvindo=bool(data.get("ouvindo", False)),
                pensando=bool(data.get("pensando", False)),
                duvida_identidade=bool(data.get("duvida_identidade", False)),
                transicao_ms=int(data.get("transicao_ms", 300)),
                versao_avatar=int(data.get("versao_avatar", 1)),
                postura_atual=str(data.get("postura_atual", "NEUTRO")),
                lado_gesto=str(data.get("lado_gesto", "none")),
                alvo_locomocao=str(data.get("alvo_locomocao", "auto")),
                acao_pet=str(data.get("acao_pet", "PATROL")),
            )
        except Exception:
            pass
    return EstadoVisualAtlas(
        modo=ModoVisual.OCIOSO,
        expressao=ExpressaoVisual.SERENO,
        intensidade_expressao=0.5,
        foco_visual="neutro",
        direcao_olhar="centro",
        gesto_atual="NENHUM",
        velocidade_movimento=0.5,
        intensidade_movimento=0.5,
        falando=False,
        ouvindo=False,
        pensando=False,
        duvida_identidade=False,
        transicao_ms=300,
        alvo_locomocao="auto",
        acao_pet="PATROL",
    )


class CognitiveResultPublisher:
    def __init__(self,path:Path,max_text_chars:int=1024):
        self.path=Path(path);self.max_text_chars=max(64,int(max_text_chars))
    def publish(self,snapshot,response):
        def text(value): return None if value is None else str(value)[:self.max_text_chars]
        payload={
            "schema_version":1,"generated_at":_utc_now(),"source_stimulus_id":snapshot.source_stimulus_id,
            "activated":bool(response.ativado),"reason":text(response.razao),"motivo":text(getattr(response,"motivo",None)),
            "texto":text(getattr(response,"texto",None)),"resumo":text(getattr(response,"resumo",None)),
            "intencao":text(getattr(response,"intencao",None)),"confianca":getattr(response,"confianca",None),
            "backend":text(getattr(response,"backend",None)),"duracao_ms":getattr(response,"duracao_ms",None),
            "requer_confirmacao":bool(getattr(response,"requer_confirmacao",False)),
            "intencao_autorizada":bool(getattr(response,"intencao_autorizada",False)),
        }
        self.path.parent.mkdir(parents=True,exist_ok=True);tmp=self.path.with_name(self.path.name+".tmp")
        try:
            with tmp.open("w",encoding="utf-8",newline="\n") as h:
                json.dump(payload,h,ensure_ascii=False,sort_keys=True,separators=(",",":"));h.write("\n");h.flush();os.fsync(h.fileno())
            os.replace(tmp,self.path)
        finally: tmp.unlink(missing_ok=True)
        return payload


class CognitiveDaemon:
    def __init__(self,snapshot_loader,context_provider,loop,publisher,*,reflection_interval_s:float=300.0,clock=time.monotonic,visual_state_sink=None,planner=None,action_policy=None,action_executor=None,action_store=None,event_sink=None,chat_inbox=None,notification_policy=None):
        if reflection_interval_s<=0: raise ValueError("reflection_interval_s must be > 0")
        self._snapshot_loader=snapshot_loader;self._context_provider=context_provider;self._loop=loop;self._publisher=publisher
        self._reflection_interval_s=float(reflection_interval_s);self._clock=clock;self._last_id=None;self._last_at=None;self._last_affective=None;self._visual_state_sink=visual_state_sink
        self._planner=planner;self._action_policy=action_policy;self._action_executor=action_executor;self._action_store=action_store;self._event_sink=event_sink;self._chat_inbox=chat_inbox;self._notification_policy=notification_policy
    def _delta(self,current):
        keys=("valencia","ativacao","estresse","confianca","engajamento","curiosidade")
        if self._last_affective is None:return 0.0
        return max((abs(float(current.get(k,0))-float(self._last_affective.get(k,0))) for k in keys),default=0.0)
    def _signals(self,snapshot,*,reflection=False):
        changes=tuple(snapshot.recent_changes or ());severities={str(x.get("severity","")).lower() for x in changes};kinds={str(x.get("kind","")).lower() for x in changes}
        novelty=max((float(x.get("novelty",0) or 0) for x in changes),default=0.0)
        return {"criticidade":"critical" in severities,"recuperacao_importante":"recovered" in kinds,"mudanca_estado":bool(kinds & {"status_changed","recovered","source_error"}),"delta_afetivo":max(0.0,min(1.0,self._delta(snapshot.affective_state))),"novidade":max(0.0,min(1.0,novelty)),"reflexao_periodica":bool(reflection)}
    def _emit_action_event(self,event_type,payload):
        if self._event_sink is not None:
            self._event_sink(event_type,dict(payload))

    def _process_action_plan(self,snapshot,response,*,trigger_kind="observation",chat_route=None):
        if getattr(response,"razao",None) is not None:
            return None
        required=(self._planner,self._action_policy,self._action_executor,self._action_store)
        if any(item is None for item in required):
            return None
        terminal={ActionStatus.COMPLETED,ActionStatus.BLOCKED,ActionStatus.FAILED,ActionStatus.CANCELLED}
        visual_types={ActionType.LOOK_AT,ActionType.SET_EXPRESSION,ActionType.SET_GESTURE,ActionType.SET_POSTURE}
        try:
            plan=self._planner.plan(snapshot.source_stimulus_id,getattr(snapshot,"entity_id",None),response,trigger_kind=trigger_kind)
            self._action_store.save_current(plan)
            self._emit_action_event("plan_created",{"plan_id":plan.plan_id,"stimulus_id":plan.stimulus_id,"objective":plan.objective,"confidence":plan.confidence})
            authorized=self._action_policy.authorize(plan,voice_enabled=False)
            self._action_store.save_current(authorized)
            for before,after in zip(plan.actions,authorized.actions):
                if before.status!=after.status or before.reason!=after.reason:
                    self._emit_action_event("action_status",{"plan_id":plan.plan_id,"action_id":after.action_id,"type":after.type.value,"status":after.status.value,"reason":after.reason,"target":after.target})
            executed=self._action_executor.execute(authorized)
            self._action_store.save_current(executed)
            for before,after in zip(authorized.actions,executed.actions):
                if before.status!=after.status or before.reason!=after.reason:
                    payload={"plan_id":plan.plan_id,"action_id":after.action_id,"type":after.type.value,"status":after.status.value,"reason":after.reason,"target":after.target}
                    self._emit_action_event("action_status",payload)
                    if after.type in visual_types:
                        self._emit_action_event("visual_action",payload)
                    if after.type is ActionType.CHAT_REPLY and after.status is ActionStatus.COMPLETED:
                        chat_payload={"plan_id":plan.plan_id,"stimulus_id":plan.stimulus_id,"role":"atlas","message":plan.response_text or ""}
                        if chat_route:
                            chat_payload.update(dict(chat_route))
                        self._emit_action_event("chat_message",chat_payload)
            if all(action.status in terminal for action in executed.actions):
                self._action_store.append_terminal(executed)
            return executed
        except Exception as exc:
            self._emit_action_event("runtime_error",{"stimulus_id":snapshot.source_stimulus_id,"error":type(exc).__name__})
            if hasattr(self._publisher,"publish_phase"):
                self._publisher.publish_phase(snapshot,state="DEGRADADA",activity="erro_plano_acao",detail=type(exc).__name__)
            return None

    def run_once(self):
        envelope=self._chat_inbox.claim_next() if self._chat_inbox is not None else None
        base_snapshot=self._snapshot_loader(); now=self._clock()
        trigger_kind="human_interaction" if envelope is not None else "observation"
        snapshot=base_snapshot
        chat_route=None
        if envelope is not None:
            chat_route={
                "channel": envelope.channel,
                "actor_id": envelope.actor_id,
                "conversation_id": envelope.conversation_id,
                "reply_target": envelope.reply_target,
            }
            snapshot=SimpleNamespace(source_stimulus_id=envelope.stimulus_id,entity_id=getattr(base_snapshot,"entity_id",None),generated_at=envelope.created_at,recent_changes=getattr(base_snapshot,"recent_changes",()),affective_state=getattr(base_snapshot,"affective_state",{}))
        reflection=envelope is None and self._last_id==snapshot.source_stimulus_id and self._last_at is not None and now-self._last_at>=self._reflection_interval_s
        if envelope is None and snapshot.source_stimulus_id==self._last_id and not reflection:return None
        thinking=False
        def inference_state(active):
            nonlocal thinking
            thinking = active
            if active and hasattr(self._publisher, "publish_phase"):
                self._publisher.publish_phase(snapshot,state="INFERINDO",activity="executando_ciclo_cognitivo",task="formular_resposta_cognitiva")
            if self._visual_state_sink is not None:
                self._visual_state_sink(EstadoInteracaoVisual(pensando=active, atualizado_em=_utc_now()))
        if hasattr(self._publisher,"publish_phase"):
            self._publisher.publish_phase(snapshot,state="ANALISANDO",activity="avaliando_estimulo")
        try:
            context=dict(self._context_provider()); signals=self._signals(snapshot,reflection=reflection)
            if envelope is not None:
                user_payload={"message_id":envelope.message_id,"stimulus_id":envelope.stimulus_id,"role":"user","message":envelope.message}
                user_payload.update(chat_route or {})
                self._emit_action_event("chat_message",user_payload)
                stimulus=build_human_stimulus(envelope.message,source=f"human.{envelope.channel}",stimulus_id=envelope.stimulus_id,timestamp=envelope.created_at,max_text_chars=512)
                recent=list(context.get("mudancas_recentes",()))
                recent.append(stimulus); context["mudancas_recentes"]=recent
                signals["interacao_humana"]=True
            response=self._loop.processar(fingerprint=snapshot.source_stimulus_id,agora=snapshot.generated_at,sinais_ativacao=signals,dados_contexto=context,on_inference=inference_state)
            if envelope is None and not reflection and self._notification_policy is not None:
                chat_route=self._notification_policy.route_for(snapshot)
            self._process_action_plan(snapshot,response,trigger_kind=trigger_kind,chat_route=chat_route)
            self._publisher.publish(snapshot,response)
            if envelope is not None:self._chat_inbox.ack(envelope.message_id)
            self._last_id=snapshot.source_stimulus_id;self._last_at=now;self._last_affective=dict(snapshot.affective_state)
            return response
        except Exception as exc:
            if envelope is not None:self._emit_action_event("runtime_error",{"stimulus_id":envelope.stimulus_id,"message_id":envelope.message_id,"error":type(exc).__name__})
            if hasattr(self._publisher,"publish_phase"):
                self._publisher.publish_phase(snapshot,state="DEGRADADA",activity="erro_cognitivo",detail=type(exc).__name__)
            raise
        finally:
            if thinking and self._visual_state_sink is not None:
                self._visual_state_sink(EstadoInteracaoVisual(pensando=False, atualizado_em=_utc_now()))



class CognitiveRuntimeOwner:
    def __init__(self,daemon,memory_store,*,poll_interval_s=.5,sleeper=time.sleep):
        self.daemon=daemon;self.memory_store=memory_store;self.poll_interval_s=float(poll_interval_s);self.sleeper=sleeper
    def start(self):
        return None
    def close(self):
        self.memory_store.close()


def build_owner(*,config_root:Path=ROOT,state_dir:Path=STATE_DIR):
    config_root=Path(config_root);state_dir=Path(state_dir);cognitive=carregar_configuracao_cognitiva(config_root/"config_cognitiva.json");hermes=load_hermes_config(config_root/"config_hermes.json")
    backend=HermesAdapter(hermes)
    gateway=LLMGateway(backend,max_payload_bytes=cognitive.contexto.max_payload_bytes,max_tokens_contexto=hermes.max_context_tokens,reasoning_policy=ReasoningPolicy())
    memory_cfg=load_memory_config(config_root/"config_memory.json");memory_store=MemoryStore(state_dir/"memory.sqlite3");retriever=MemoryRetriever(memory_store,max_items=memory_cfg.retriever_max_items,max_bytes=memory_cfg.retriever_max_bytes)
    cache=CognitiveCache(load_cache_config(config_root/"config_cache.json"));policy=ActivationPolicy(cognitive.ativacao);builder=ContextoCognitivoBuilder(cognitive.contexto);capabilities=PolicyCapabilities(atlas_capability_registry(),read_auto_allow=("get_host_status",),control_allow=("restart_service",),auto_control_allow=("restart_service",),auto_hosts=("pentium",),auto_services=("atlas-observation.service","atlas-dashboard.service"))
    loop=ReactionLoopCognitivo(policy,builder,gateway,capability_policy=capabilities,memory_retriever=retriever,cognitive_cache=cache)
    expected_sha=(os.environ.get("ATLAS_EXPECTED_SHA") or None) if cognitive.observation_bridge.require_expected_sha else None
    snapshot_path=Path(os.path.expanduser(cognitive.observation_bridge.snapshot_path));provider=HumanContextProvider(state_dir/"observation-affective-health.json",snapshot_path,max_snapshot_age_s=cognitive.observation_bridge.max_snapshot_age_s,expected_sha=expected_sha)
    visual_sink=InteractionDatagramClient(state_dir/"cognitive-interaction.sock").send
    observable=CognitiveObservablePublisher(state_dir/"cognitive-runtime.json",state_dir/"cognitive-activity.jsonl",max_events=64,max_text_chars=cognitive.contexto.max_string_chars)
    action_events=CognitiveActionEventPublisher(state_dir/"dashboard-events.jsonl",max_events=128,max_bytes=262144)
    action_store=ActionPlanStore(state_dir/"action-plan-current.json",state_dir/"action-plan-history.jsonl",max_history=64,max_bytes=131072)
    action_planner=ActionPlanner()
    action_policy=ActionPolicy(capabilities)
    visual_state_path=state_dir/"visual-state.json"
    visual_publisher=VisualStatePublisher(visual_state_path)
    autonomy_executor=SafeLocalCapabilityExecutor(host="pentium",services=("atlas-observation.service","atlas-dashboard.service"),on_executed=capabilities.registrar_execucao)
    action_executor=ActionExecutorRegistry(
        visual_getter=lambda: read_visual_state(visual_state_path),
        visual_writer=visual_publisher.publicar,
        capability_sink=autonomy_executor,
        event_sink=action_events.publish,
    )
    chat_inbox=ChatInbox(state_dir/"chat-inbox.json",max_items=32,max_message_chars=512)
    notification_policy=load_notification_policy(config_root)
    daemon=CognitiveDaemon(lambda:load_cognitive_observation_snapshot(snapshot_path),provider,loop,observable,visual_state_sink=visual_sink,planner=action_planner,action_policy=action_policy,action_executor=action_executor,action_store=action_store,event_sink=action_events.publish,chat_inbox=chat_inbox,notification_policy=notification_policy)
    return CognitiveRuntimeOwner(daemon,memory_store)


def main()->int:
    owner=build_owner();stop=False
    def request_stop(*_):
        nonlocal stop;stop=True
    signal.signal(signal.SIGTERM,request_stop);signal.signal(signal.SIGINT,request_stop)
    try:
        owner.start();print("ATLAS_COGNITIVE_DAEMON_READY",flush=True)
        while not stop:
            try: owner.daemon.run_once()
            except FileNotFoundError: pass
            except Exception as exc: print(f"ATLAS_COGNITIVE_DEGRADED type={type(exc).__name__}",flush=True)
            owner.sleeper(owner.poll_interval_s)
    finally: owner.close()
    return 0

if __name__=="__main__": raise SystemExit(main())
