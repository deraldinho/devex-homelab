from __future__ import annotations

import json
import os
import signal
import time
from datetime import datetime, timezone
from pathlib import Path

from .capability_registry import atlas_capability_registry
from .affective_interaction_ipc import InteractionDatagramClient
from .cognitive_cache import CognitiveCache
from .cognitive_observability import CognitiveObservablePublisher
from .config_cache import load_cache_config
from .config_memory import load_memory_config
from .config_llama_server import carregar_configuracao_llama_server
from .configuracao_cognitiva import carregar_configuracao_cognitiva
from .configuracao_llm import carregar_configuracao_llm
from .contexto_cognitivo import ContextoCognitivoBuilder
from .cognitive_observation_projection import load_cognitive_observation_snapshot
from .human_context import HumanContextProvider
from .llama_cpp_backend import LlamaCppBackend
from .llama_cpp_resident_backend import LlamaCppResidentBackend
from .llama_server_runtime import LlamaCppServerRuntime
from .llm_gateway import LLMGateway
from .memory_retriever import MemoryRetriever
from .memory_store import MemoryStore
from .modelo_visual_atlas import EstadoInteracaoVisual
from .policy_capabilities import PolicyCapabilities
from .politica_ativacao_cognitiva import ActivationPolicy
from .reaction_loop_cognitivo import ReactionLoopCognitivo
from .reasoning_policy import ReasoningPolicy

ROOT=Path(__file__).resolve().parent
AGENT_ROOT=Path.home()/"pentium-agent"
STATE_DIR=AGENT_ROOT/"atlas"/"runtime"


def _utc_now()->str:
    return datetime.now(timezone.utc).isoformat()


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
    def __init__(self,snapshot_loader,context_provider,loop,publisher,*,reflection_interval_s:float=300.0,clock=time.monotonic,visual_state_sink=None):
        if reflection_interval_s<=0: raise ValueError("reflection_interval_s must be > 0")
        self._snapshot_loader=snapshot_loader;self._context_provider=context_provider;self._loop=loop;self._publisher=publisher
        self._reflection_interval_s=float(reflection_interval_s);self._clock=clock;self._last_id=None;self._last_at=None;self._last_affective=None;self._visual_state_sink=visual_state_sink
    def _delta(self,current):
        keys=("valencia","ativacao","estresse","confianca","engajamento","curiosidade")
        if self._last_affective is None:return 0.0
        return max((abs(float(current.get(k,0))-float(self._last_affective.get(k,0))) for k in keys),default=0.0)
    def _signals(self,snapshot,*,reflection=False):
        changes=tuple(snapshot.recent_changes or ());severities={str(x.get("severity","")).lower() for x in changes};kinds={str(x.get("kind","")).lower() for x in changes}
        novelty=max((float(x.get("novelty",0) or 0) for x in changes),default=0.0)
        return {"criticidade":"critical" in severities,"recuperacao_importante":"recovered" in kinds,"mudanca_estado":bool(kinds & {"status_changed","recovered","source_error"}),"delta_afetivo":max(0.0,min(1.0,self._delta(snapshot.affective_state))),"novidade":max(0.0,min(1.0,novelty)),"reflexao_periodica":bool(reflection)}
    def run_once(self):
        snapshot=self._snapshot_loader();now=self._clock();reflection=self._last_id==snapshot.source_stimulus_id and self._last_at is not None and now-self._last_at>=self._reflection_interval_s
        if snapshot.source_stimulus_id==self._last_id and not reflection:return None
        if hasattr(self._publisher,"publish_phase"):
            self._publisher.publish_phase(snapshot,state="ANALISANDO",activity="avaliando_estimulo")
        context=self._context_provider();signals=self._signals(snapshot,reflection=reflection)
        if hasattr(self._publisher,"publish_phase"):
            self._publisher.publish_phase(snapshot,state="INFERINDO",activity="executando_ciclo_cognitivo",task="formular_resposta_cognitiva")
        if self._visual_state_sink is not None:
            self._visual_state_sink(EstadoInteracaoVisual(pensando=True, atualizado_em=_utc_now()))
        try:
            response=self._loop.processar(fingerprint=snapshot.source_stimulus_id,agora=snapshot.generated_at,sinais_ativacao=signals,dados_contexto=context)
            self._publisher.publish(snapshot,response);self._last_id=snapshot.source_stimulus_id;self._last_at=now;self._last_affective=dict(snapshot.affective_state)
            return response
        except Exception as exc:
            if hasattr(self._publisher,"publish_phase"):
                self._publisher.publish_phase(snapshot,state="DEGRADADA",activity="erro_cognitivo",detail=type(exc).__name__)
            raise
        finally:
            if self._visual_state_sink is not None:
                self._visual_state_sink(EstadoInteracaoVisual(pensando=False, atualizado_em=_utc_now()))


class CognitiveRuntimeOwner:
    def __init__(self,daemon,server,memory_store,*,poll_interval_s=.5,startup_timeout_s=15.0,sleeper=time.sleep):
        self.daemon=daemon;self.server=server;self.memory_store=memory_store;self.poll_interval_s=float(poll_interval_s);self.startup_timeout_s=float(startup_timeout_s);self.sleeper=sleeper
    def start(self,socket_path:Path):
        self.server.start();deadline=time.monotonic()+self.startup_timeout_s
        while not Path(socket_path).exists():
            if time.monotonic()>=deadline: raise TimeoutError("atlas llama-server socket startup timeout")
            self.sleeper(.1)
    def close(self):
        try:self.server.stop()
        finally:self.memory_store.close()


def build_owner(*,config_root:Path=ROOT,state_dir:Path=STATE_DIR):
    config_root=Path(config_root);state_dir=Path(state_dir);cognitive=carregar_configuracao_cognitiva(config_root/"config_cognitiva.json");llm=carregar_configuracao_llm(config_root/"config_llm.json");server_cfg=carregar_configuracao_llama_server(config_root/"config_llama_server.json")
    runtime_root=AGENT_ROOT/"runtime";model_path=(AGENT_ROOT/llm.modelo_path).resolve();binary=runtime_root/"llama"/"build"/"bin"/"llama-server";cli=runtime_root/"llama"/"build"/"bin"/"llama-cli";socket_path=Path(server_cfg.socket_path)
    server=LlamaCppServerRuntime(binary,model_path,socket_path,context_size=server_cfg.context_size,cache_reuse=server_cfg.cache_reuse)
    fallback=LlamaCppBackend(cli,model_path,timeout_s=llm.timeout_s,max_saida_bytes=llm.max_saida_bytes)
    backend=LlamaCppResidentBackend(socket_path,cache_reuse=server_cfg.cache_reuse,timeout_s=llm.timeout_s,max_response_bytes=server_cfg.max_response_bytes,fallback=fallback)
    gateway=LLMGateway(backend,max_payload_bytes=cognitive.contexto.max_payload_bytes,max_tokens_contexto=llm.max_tokens_contexto,reasoning_policy=ReasoningPolicy())
    memory_cfg=load_memory_config(config_root/"config_memory.json");memory_store=MemoryStore(state_dir/"memory.sqlite3");retriever=MemoryRetriever(memory_store,max_items=memory_cfg.retriever_max_items,max_bytes=memory_cfg.retriever_max_bytes)
    cache=CognitiveCache(load_cache_config(config_root/"config_cache.json"));policy=ActivationPolicy(cognitive.ativacao);builder=ContextoCognitivoBuilder(cognitive.contexto);capabilities=PolicyCapabilities(atlas_capability_registry(),read_auto_allow=("get_host_status",),control_allow=())
    loop=ReactionLoopCognitivo(policy,builder,gateway,capability_policy=capabilities,memory_retriever=retriever,cognitive_cache=cache)
    expected_sha=(os.environ.get("ATLAS_EXPECTED_SHA") or None) if cognitive.observation_bridge.require_expected_sha else None
    snapshot_path=Path(os.path.expanduser(cognitive.observation_bridge.snapshot_path));provider=HumanContextProvider(state_dir/"observation-affective-health.json",snapshot_path,max_snapshot_age_s=cognitive.observation_bridge.max_snapshot_age_s,expected_sha=expected_sha)
    visual_sink=InteractionDatagramClient(state_dir/"cognitive-interaction.sock").send
    observable=CognitiveObservablePublisher(state_dir/"cognitive-runtime.json",state_dir/"cognitive-activity.jsonl",max_events=64,max_text_chars=cognitive.contexto.max_string_chars)
    daemon=CognitiveDaemon(lambda:load_cognitive_observation_snapshot(snapshot_path),provider,loop,observable,visual_state_sink=visual_sink)
    return CognitiveRuntimeOwner(daemon,server,memory_store),socket_path


def main()->int:
    owner,socket_path=build_owner();stop=False
    def request_stop(*_):
        nonlocal stop;stop=True
    signal.signal(signal.SIGTERM,request_stop);signal.signal(signal.SIGINT,request_stop)
    try:
        owner.start(socket_path);print("ATLAS_COGNITIVE_DAEMON_READY",flush=True)
        while not stop:
            try: owner.daemon.run_once()
            except FileNotFoundError: pass
            except Exception as exc: print(f"ATLAS_COGNITIVE_DEGRADED type={type(exc).__name__}",flush=True)
            owner.sleeper(owner.poll_interval_s)
    finally: owner.close()
    return 0

if __name__=="__main__": raise SystemExit(main())
