from __future__ import annotations

import hashlib
import json
import os
import signal
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

try:
    from agent.cli import load_config as load_agent_config, _managed_host_from_config
    from agent.control_audit import ControlAuditJournal
    from agent.managed_control import ManagedControlService
    from agent.managed_inventory import ManagedInventory
    from agent.ssh_transport import SshTransport
except ImportError:
    from infrastructure.pentium.agent.cli import load_config as load_agent_config, _managed_host_from_config
    from infrastructure.pentium.agent.control_audit import ControlAuditJournal
    from infrastructure.pentium.agent.managed_control import ManagedControlService
    from infrastructure.pentium.agent.managed_inventory import ManagedInventory
    from infrastructure.pentium.agent.ssh_transport import SshTransport

from .capability_registry import atlas_capability_registry
from .action_executors import ActionExecutorRegistry
from .autonomy_executor import SafeLocalCapabilityExecutor
from .multi_host_executor import CanonicalHealthVerifier, MultiHostCapabilityExecutor
from .discord_capability_executor import DiscordCapabilityExecutor
from .git_capability_executor import GitCapabilityExecutor, ClusterVitalsExecutor
from .l2j_observation import L2jCapabilityExecutor
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
from .behavior_selector import BehaviorSelector
from .continuous_intent_machine import ContinuousIntentMachine
from .continuous_intent_publisher import ContinuousIntentPublisher
from .habituation_engine import HabituationEngine
from .workspace_policy import WorkspacePolicy
from .workspace_broker import WorkspaceBroker
from .workspace_index import WorkspaceIndex
from .workspace_retriever import WorkspaceRetriever
from .workspace_context_cache import WorkspaceContextCache
from .workspace_capability_executor import WorkspaceCapabilityExecutor
from .capability_dispatch import CapabilityDispatcher
from .workspace_health import WorkspaceEconomyPublisher
from .token_budget_governor import TokenBudgetGovernor
from .cognitive_router import CognitiveRouter
from .self_work import SelfWorkRuntime
from .task_store import SelfWorkStore
from .task_capability_executor import TaskCapabilityExecutor

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
    def __init__(self,snapshot_loader,context_provider,loop,publisher,*,reflection_interval_s:float=300.0,clock=time.monotonic,visual_state_sink=None,planner=None,action_policy=None,action_executor=None,action_store=None,event_sink=None,chat_inbox=None,notification_policy=None,behavior_selector=None,intent_machine=None,habituation_engine=None,intent_publisher=None,cognitive_router=None,self_work_runtime=None):
        if reflection_interval_s<=0: raise ValueError("reflection_interval_s must be > 0")
        self._snapshot_loader=snapshot_loader;self._context_provider=context_provider;self._loop=loop;self._publisher=publisher
        self._reflection_interval_s=float(reflection_interval_s);self._clock=clock;self._last_id=None;self._last_at=None;self._last_affective=None;self._visual_state_sink=visual_state_sink
        self._planner=planner;self._action_policy=action_policy;self._action_executor=action_executor;self._action_store=action_store;self._event_sink=event_sink;self._chat_inbox=chat_inbox;self._notification_policy=notification_policy
        self._behavior_selector=behavior_selector;self._intent_machine=intent_machine;self._habituation_engine=habituation_engine;self._intent_publisher=intent_publisher
        self._cognitive_router=cognitive_router;self._self_work_runtime=self_work_runtime
        self._dialogue_history = {}
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

    def _material_fingerprint(self,snapshot):
        focus=dict(getattr(snapshot,"focus",{}) or {});principal=dict(focus.get("principal") or {})
        payload={"assunto_id":principal.get("assunto_id"),"entidade_id":principal.get("entidade_id"),"gravidade":principal.get("gravidade"),"critico":principal.get("critico"),"recuperado":principal.get("recuperado"),"incident":getattr(snapshot,"incident",None)}
        raw=json.dumps(payload,ensure_ascii=True,sort_keys=True,separators=(",",":"),default=str).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _continuous_behavior(self,snapshot,*,human_interaction=False,now=None):
        required=(self._behavior_selector,self._intent_machine,self._habituation_engine)
        if any(item is None for item in required): return "normal",None,""
        try:
            current=self._intent_machine.current
            habituation=self._habituation_engine.level(current) if current is not None else 0.0
            decision=self._behavior_selector.select(snapshot,human_interaction=human_interaction,habituation=habituation)
            transition=self._intent_machine.update(decision,snapshot,now=now or snapshot.generated_at,human_interaction=human_interaction)
            intent=transition.intent;fingerprint=self._material_fingerprint(snapshot);mode="normal"
            if intent is not None:
                habit=self._habituation_engine.evaluate(intent,fingerprint,terminal=intent.terminal)
                if human_interaction: mode="normal"
                elif intent.terminal: mode="terminal" if habit.allow_message else "silent_tracking"
                elif not habit.allow_message: mode="silent_tracking"
            if self._intent_publisher is not None:
                self._intent_publisher.publish(intent,communication_mode=mode,material_fingerprint=fingerprint)
            return mode,intent,fingerprint
        except Exception as exc:
            self._emit_action_event("continuous_intent_error",{"error":type(exc).__name__})
            if self._intent_publisher is not None:
                try:
                    self._intent_publisher.publish(None,communication_mode="normal",material_fingerprint="")
                except Exception as publish_exc:
                    self._emit_action_event("continuous_intent_publish_error",{"error":type(publish_exc).__name__})
            return "normal",None,""

    def _process_action_plan(self,snapshot,response,*,trigger_kind="observation",chat_route=None,communication_mode="normal"):
        if getattr(response,"razao",None) is not None and communication_mode!="silent_tracking":
            return None
        required=(self._planner,self._action_policy,self._action_executor,self._action_store)
        if any(item is None for item in required):
            return None
        terminal={ActionStatus.COMPLETED,ActionStatus.BLOCKED,ActionStatus.FAILED,ActionStatus.CANCELLED}
        visual_types={ActionType.LOOK_AT,ActionType.SET_EXPRESSION,ActionType.SET_GESTURE,ActionType.SET_POSTURE}
        try:
            plan=self._planner.plan(snapshot.source_stimulus_id,getattr(snapshot,"entity_id",None),response,trigger_kind=trigger_kind,communication_mode=communication_mode)
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
                "client_message_id": getattr(envelope, "client_message_id", None),
            }
            snapshot=SimpleNamespace(source_stimulus_id=envelope.stimulus_id,entity_id=getattr(base_snapshot,"entity_id",None),generated_at=envelope.created_at,recent_changes=getattr(base_snapshot,"recent_changes",()),affective_state=getattr(base_snapshot,"affective_state",{}))
        reflection=envelope is None and self._last_id==snapshot.source_stimulus_id and self._last_at is not None and now-self._last_at>=self._reflection_interval_s
        if envelope is None and snapshot.source_stimulus_id==self._last_id and not reflection:return None
        self_work_preempted=False
        if envelope is not None and self._self_work_runtime is not None and self._self_work_runtime.current is not None:
            try:
                self._self_work_runtime.pause_for_human(now=snapshot.generated_at);self_work_preempted=True
            except Exception as exc:
                self._emit_action_event("self_work_preempt_error",{"error":type(exc).__name__})
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
                msg_lower=envelope.message.lower()
                status_query_keywords=("como está","como esta","qual o status","qual o estado","relatório","relatorio","saúde","saude","backup","servidores e o status","status dos")
                if any(kw in msg_lower for kw in status_query_keywords):
                    recent=list(context.get("mudancas_recentes",()))
                    recent.append(stimulus)
                    context["mudancas_recentes"]=recent
                else:
                    context["mudancas_recentes"]=[stimulus]
                    context["dependencias_afetadas"]=()
                conv_key = str(getattr(envelope, "conversation_id", None) or getattr(envelope, "channel", None) or "default")
                context["historico_conversa"] = list(self._dialogue_history.get(conv_key, ()))
                signals["interacao_humana"]=True
            communication_mode,intent,material_fingerprint=self._continuous_behavior(
                base_snapshot,human_interaction=envelope is not None,now=snapshot.generated_at,
            )
            self_work_cycle=False
            if intent is not None and getattr(getattr(intent,"tipo",None),"value",None)=="SELF_WORK" and self._self_work_runtime is not None:
                self_work_cycle=True
                if self._self_work_runtime.current is None:
                    area=str(getattr(intent,"assunto_id","scratch")).split(":",1)[-1] or "scratch"
                    try:
                        self._self_work_runtime.propose(getattr(intent,"motivo","self_work"),area,now=snapshot.generated_at)
                        self._self_work_runtime.activate(now=snapshot.generated_at)
                    except Exception as exc:
                        self._emit_action_event("self_work_start_error",{"error":type(exc).__name__})
            if self._cognitive_router is not None:
                kind="human" if envelope is not None else ("incident" if getattr(base_snapshot,"incident",None) else ("self_work" if self_work_cycle else ("reflection" if reflection else "observation")))
                route=self._cognitive_router.route(kind=kind,fingerprint=material_fingerprint or self._material_fingerprint(base_snapshot),deadline_due=reflection)
                if getattr(route,"value",str(route))=="no_inference_required":
                    self._last_id=snapshot.source_stimulus_id;self._last_at=now;self._last_affective=dict(snapshot.affective_state)
                    if self_work_preempted and self._self_work_runtime is not None and self._self_work_runtime.current is not None:
                        self._self_work_runtime.resume_if_valid(now=snapshot.generated_at)
                    return None
            response=self._loop.processar(fingerprint=snapshot.source_stimulus_id,agora=snapshot.generated_at,sinais_ativacao=signals,dados_contexto=context,on_inference=inference_state)

            # ReAct Recursion Loop: se houver capability de leitura autorizada para interação humana, executa e sintetiza
            if envelope is not None and response is not None and getattr(response, "intencao", None):
                read_prefixes = ("l2j_", "git_", "get_cluster_vitals", "get_host_status", "workspace_", "task_")
                is_read_query = (
                    any(str(response.intencao).startswith(p) for p in read_prefixes)
                    and getattr(response, "intencao_autorizada", False)
                    and not getattr(response, "requer_confirmacao", False)
                )
                if is_read_query:
                    cap_sink = getattr(self._action_executor, "_capability_sink", None)
                    if cap_sink is not None:
                        try:
                            tool_result = cap_sink(str(response.intencao), dict(response.parametros_intencao or {}))
                            if tool_result is not None:
                                react_context = dict(context)
                                react_context["observacoes_ferramentas"] = [
                                    {"capability": str(response.intencao), "result": tool_result}
                                ]
                                synthesis_resp = self._loop.processar(
                                    fingerprint=f"{snapshot.source_stimulus_id}:react_synthesis",
                                    agora=snapshot.generated_at,
                                    sinais_ativacao=signals,
                                    dados_contexto=react_context,
                                    on_inference=inference_state,
                                )
                                if synthesis_resp is not None and getattr(synthesis_resp, "texto", None):
                                    response = synthesis_resp
                        except Exception as exc:
                            self._emit_action_event("react_loop_error", {"capability": str(response.intencao), "error": type(exc).__name__})

            if self_work_cycle and self._self_work_runtime is not None and self._self_work_runtime.current is not None:
                current=self._self_work_runtime.current
                if getattr(current.state,"value","")=="ACTIVE": self._self_work_runtime.begin_work(now=snapshot.generated_at)
                if self._self_work_runtime.current is not None: self._self_work_runtime.record_inference(now=snapshot.generated_at)
            if envelope is None and not reflection and self._notification_policy is not None:
                chat_route=self._notification_policy.route_for(base_snapshot)
            self._process_action_plan(snapshot,response,trigger_kind=trigger_kind,chat_route=chat_route,communication_mode=communication_mode)
            self._publisher.publish(snapshot,response)
            if envelope is not None:
                if response is not None and getattr(response, "texto", None):
                    conv_key = str(getattr(envelope, "conversation_id", None) or getattr(envelope, "channel", None) or "default")
                    hist = self._dialogue_history.setdefault(conv_key, [])
                    hist.append({"role": "user", "message": str(envelope.message)})
                    hist.append({"role": "atlas", "message": str(response.texto)})
                    if len(hist) > 10:
                        self._dialogue_history[conv_key] = hist[-10:]
                self._chat_inbox.ack(envelope.message_id)
                if self_work_preempted and self._self_work_runtime is not None and self._self_work_runtime.current is not None:
                    try: self._self_work_runtime.resume_if_valid(now=snapshot.generated_at)
                    except Exception as exc: self._emit_action_event("self_work_resume_error",{"error":type(exc).__name__})
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
    def __init__(self,daemon,memory_store,*,health_publisher=None,health_dependencies=None,closeables=(),poll_interval_s=.5,sleeper=time.sleep):
        self.daemon=daemon;self.memory_store=memory_store;self.poll_interval_s=float(poll_interval_s);self.sleeper=sleeper
        self._health_publisher=health_publisher;self._health_dependencies=dict(health_dependencies or {});self._closeables=tuple(closeables)
    def start(self):
        return None
    def run_once(self):
        try:
            return self.daemon.run_once()
        finally:
            if self._health_publisher is not None:
                self._health_publisher.publish(**self._health_dependencies)
    def close(self):
        for item in reversed(self._closeables):
            try: item.close()
            except Exception: pass
        self.memory_store.close()


def build_owner(*,config_root:Path=ROOT,state_dir:Path=STATE_DIR):
    config_root=Path(config_root);state_dir=Path(state_dir);cognitive=carregar_configuracao_cognitiva(config_root/"config_cognitiva.json");hermes=load_hermes_config(config_root/"config_hermes.json")
    governor=TokenBudgetGovernor(window_budget=120000)
    router=CognitiveRouter(governor)
    backend=HermesAdapter(hermes)
    gateway=LLMGateway(backend,max_payload_bytes=cognitive.contexto.max_payload_bytes,max_tokens_contexto=hermes.max_context_tokens,reasoning_policy=ReasoningPolicy(),token_recorder=lambda total:governor.record(total,category="llm"))
    memory_cfg=load_memory_config(config_root/"config_memory.json");memory_store=MemoryStore(state_dir/"memory.sqlite3");retriever=MemoryRetriever(memory_store,max_items=memory_cfg.retriever_max_items,max_bytes=memory_cfg.retriever_max_bytes)
    workspace_root=AGENT_ROOT/"atlas-workspace"
    workspace_policy=WorkspacePolicy();workspace_broker=WorkspaceBroker(workspace_root,workspace_policy)
    workspace_index=WorkspaceIndex(workspace_root/".system"/"index.sqlite3")
    workspace_cache=WorkspaceContextCache(workspace_root/".system"/"context-cache.sqlite3",ttl_s=300,max_entries=256)
    workspace_retriever=WorkspaceRetriever(workspace_index,cache=workspace_cache)
    self_work_store=SelfWorkStore(state_dir/"self-work-current.json",state_dir/"self-work-history.jsonl")
    self_work=SelfWorkRuntime(ttl_s=300,max_operations=20,max_inferences=2,store=self_work_store)
    try: self_work.restore_from_store(now=_utc_now().isoformat())
    except Exception: pass
    task_executor=TaskCapabilityExecutor(self_work)
    cache=CognitiveCache(load_cache_config(config_root/"config_cache.json"));policy=ActivationPolicy(cognitive.ativacao);builder=ContextoCognitivoBuilder(cognitive.contexto)
    capabilities=PolicyCapabilities(atlas_capability_registry(),read_auto_allow=("get_host_status","get_cluster_vitals","l2j_get_status","l2j_get_dashboards","l2j_check_jvm","l2j_docker_stats","l2j_get_logs","l2j_run_tests","l2j_inspect_persistence","git_get_status","git_recent_commits","workspace_status","workspace_list","workspace_read","workspace_search","task_status"),control_allow=(),auto_control_allow=("restart_service","restart_container"),auto_service_targets=(("pentium","atlas-observation.service"),("pentium","atlas-dashboard.service")),auto_container_targets=(),auto_unscoped_control_allow=("workspace_create_note","workspace_write","workspace_append","workspace_mkdir","workspace_move","workspace_archive","workspace_trash","workspace_restore","discord_create_channel","discord_rename_channel","discord_send_alert","discord_create_note","discord_create_incident","discord_resolve_incident","task_create","task_complete","task_abandon"))
    loop=ReactionLoopCognitivo(policy,builder,gateway,capability_policy=capabilities,memory_retriever=retriever,workspace_retriever=workspace_retriever,cognitive_cache=cache)
    expected_sha=(os.environ.get("ATLAS_EXPECTED_SHA") or None) if cognitive.observation_bridge.require_expected_sha else None
    snapshot_path=Path(os.path.expanduser(cognitive.observation_bridge.snapshot_path));provider=HumanContextProvider(state_dir/"observation-affective-health.json",snapshot_path,max_snapshot_age_s=cognitive.observation_bridge.max_snapshot_age_s,expected_sha=expected_sha)
    visual_sink=InteractionDatagramClient(state_dir/"cognitive-interaction.sock").send
    observable=CognitiveObservablePublisher(state_dir/"cognitive-runtime.json",state_dir/"cognitive-activity.jsonl",max_events=64,max_text_chars=cognitive.contexto.max_string_chars)
    action_events=CognitiveActionEventPublisher(state_dir/"dashboard-events.jsonl",max_events=128,max_bytes=262144)
    action_store=ActionPlanStore(state_dir/"action-plan-current.json",state_dir/"action-plan-history.jsonl",max_history=64,max_bytes=131072)
    action_planner=ActionPlanner();action_policy=ActionPolicy(capabilities)
    visual_state_path=state_dir/"visual-state.json";visual_publisher=VisualStatePublisher(visual_state_path)
    agent_config_path=AGENT_ROOT/"agent"/"config.json"
    agent_payload=load_agent_config(agent_config_path)
    managed_inventory=ManagedInventory([
        _managed_host_from_config(item) for item in agent_payload["managed_hosts"]
    ])
    managed_control=ManagedControlService(
        managed_inventory,
        SshTransport(),
        ControlAuditJournal(
            Path(str(agent_payload.get("control_audit_file", "~/.local/state/devex-homelab/control-audit.jsonl"))).expanduser()
        ),
    )
    local_autonomy_executor=SafeLocalCapabilityExecutor(
        host="pentium",
        services=("atlas-observation.service","atlas-dashboard.service"),
    )
    autonomy_executor=MultiHostCapabilityExecutor(
        local_autonomy_executor,
        managed_control,
        managed_inventory,
        verifier=CanonicalHealthVerifier(
            state_dir/"health-supervisor.json",
            timeout_s=20.0,
            poll_interval_s=0.5,
        ),
        on_executed=capabilities.registrar_execucao,
    )
    workspace_executor=WorkspaceCapabilityExecutor(workspace_broker,searcher=workspace_retriever,indexer=workspace_index,self_work=self_work)
    discord_executor=DiscordCapabilityExecutor(state_dir/"discord-action-queue.jsonl")
    git_executor=GitCapabilityExecutor()
    vitals_executor=ClusterVitalsExecutor(state_dir)
    l2j_executor=L2jCapabilityExecutor()
    dispatcher=CapabilityDispatcher(autonomy_executor,workspace_executor,discord_executor,git_executor=git_executor,vitals_executor=vitals_executor,l2j_executor=l2j_executor,task_executor=task_executor)
    action_executor=ActionExecutorRegistry(visual_getter=lambda:read_visual_state(visual_state_path),visual_writer=visual_publisher.publicar,capability_sink=dispatcher,event_sink=action_events.publish)
    chat_inbox=ChatInbox(state_dir/"chat-inbox.json",max_items=32,max_message_chars=512);notification_policy=load_notification_policy(config_root)
    behavior_selector=BehaviorSelector();intent_machine=ContinuousIntentMachine(ttl_s=300.0,activation_threshold=.5);habituation_engine=HabituationEngine(max_entries=64,ttl_s=300.0);intent_publisher=ContinuousIntentPublisher(state_dir/"continuous-intent.json")
    daemon=CognitiveDaemon(lambda:load_cognitive_observation_snapshot(snapshot_path),provider,loop,observable,visual_state_sink=visual_sink,planner=action_planner,action_policy=action_policy,action_executor=action_executor,action_store=action_store,event_sink=action_events.publish,chat_inbox=chat_inbox,notification_policy=notification_policy,behavior_selector=behavior_selector,intent_machine=intent_machine,habituation_engine=habituation_engine,intent_publisher=intent_publisher,cognitive_router=router,self_work_runtime=self_work)
    health=WorkspaceEconomyPublisher(state_dir/"workspace-economy-health.json")
    deps={"broker":workspace_broker,"governor":governor,"router":router,"self_work":self_work,"expected_sha":expected_sha}
    return CognitiveRuntimeOwner(daemon,memory_store,health_publisher=health,health_dependencies=deps,closeables=(workspace_index,workspace_cache))

def main()->int:
    owner=build_owner();stop=False
    def request_stop(*_):
        nonlocal stop;stop=True
    signal.signal(signal.SIGTERM,request_stop);signal.signal(signal.SIGINT,request_stop)
    try:
        owner.start();print("ATLAS_COGNITIVE_DAEMON_READY",flush=True)
        while not stop:
            try: owner.run_once()
            except FileNotFoundError: pass
            except Exception as exc: print(f"ATLAS_COGNITIVE_DEGRADED type={type(exc).__name__}",flush=True)
            owner.sleeper(owner.poll_interval_s)
    finally: owner.close()
    return 0

if __name__=="__main__": raise SystemExit(main())
