"""LLM-grounded conversational alerts from Atlas, not from the Hermes Discord gateway.

Strictly observational: Hermes is the inference worker; Atlas decides, validates
and sends through its own native Discord queue. Never executes a model intention.
"""
from __future__ import annotations

import json
import math
import re
import subprocess
from pathlib import Path

_METRICS=("valencia","ativacao","estresse","confianca","engajamento","curiosidade")
_VALID_EVENT_KINDS={"model_pool_health","incident","recovery","security_finding"}
_BLOCKED=re.compile(r"(?i)(?:nvapi-|sk-proj-|ghp_|github_pat_|\\b(?:token|password|secret|api_key)\\s*[:=]|@everyone|@here|<@!?\\d+>)")
_NUMBER=re.compile(r"(?<![a-zA-Z])\\d+(?:[.,]\\d+)?(?:\\s*%)?")
class NarrationUnavailable(RuntimeError):
    pass

def safe_context(runtime_dir):
    """Only curated metadata, no user messages, logs, IPs, names, or raw payload."""
    root=Path(runtime_dir)
    result={"affective_state":{},"observations":[]}
    try:
        p=root/"affective-state.json"
        if p.is_file() and not p.is_symlink() and p.stat().st_size<=8192:
            data=json.loads(p.read_text(encoding="utf-8"))
            values=data.get("estado") or {}
            for k in _METRICS:
                v=values.get(k)
                if isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and (-1<=v<=1 if k=="valencia" else 0<=v<=1):
                    result["affective_state"][k]=round(float(v),3)
    except (OSError,ValueError,TypeError):
        pass
    try:
        p=root/"cognitive-observation-context.json"
        if p.is_file() and not p.is_symlink() and p.stat().st_size<=131072:
            doc=json.loads(p.read_text(encoding="utf-8"))
            for ev in (doc.get("recent_changes") or [])[-6:]:
                if not isinstance(ev,dict):continue
                severity=ev.get("severity");kind=ev.get("kind")
                if severity in ("info","notice","warning","critical") and isinstance(kind,str) and re.fullmatch(r"[a-z][a-z0-9_-]{0,45}",kind):
                    result["observations"].append({"severity":severity,"kind":kind})
    except (OSError,ValueError,TypeError):
        pass
    return result

def validate_voice(message, facts):
    if not isinstance(message,str):
        raise NarrationUnavailable("invalid_narrative")
    message=message.strip()
    if not 18<=len(message)<=850 or "\n" in message or _BLOCKED.search(message):
        raise NarrationUnavailable("narrative_policy_denied")
    if any(w in message.casefold() for w in ("eu verifiquei todos os servidores","estou consciente","sinto dor","custo de","não houve cobrança","sem custo","cobrança confirmada","quota disponível","cota disponível","não derrubou","não houve falhas","tudo funcionando","tudo estável")) or "r$" in message.casefold() or "us$" in message.casefold():
        raise NarrationUnavailable("unverified_or_subjective_claim")
    # Reject novel numbers. Model is not allowed to add statistics or invented times.
    allowed=set(_NUMBER.findall(" ".join(str(v) for v in facts.values() if isinstance(v,(int,float,str)))))
    given=set(_NUMBER.findall(message))
    if not given.issubset(allowed):
        raise NarrationUnavailable("unverified_numerical_claim")
    if "catalog_nvidia" in facts and re.search(r"(?i)\\b(?:source.error|incidente|errinho|falha\\s+(?:na|no|dos)\\s+servidores)\\b",message):
        raise NarrationUnavailable("unverified_incident_claim")
    # All required grounded numeric facts must be present in the message.
    for name in ("candidates","catalog_nous","catalog_nvidia"):
        if name in facts and str(facts[name]) not in message:
            raise NarrationUnavailable("required_fact_missing")
    return message

class AtlasNaturalNarrator:
    def __init__(self,*,hermes_binary=None,runtime_dir,runner=subprocess.run,timeout=50):
        self.binary=str(hermes_binary or (Path.home()/".local"/"bin"/"hermes"))
        self.runtime_dir=Path(runtime_dir)
        self.runner=runner
        self.timeout=timeout
    def narrate(self,event,*,kind="model_pool_health"):
        if kind not in _VALID_EVENT_KINDS or not isinstance(event,dict):
            raise NarrationUnavailable("invalid_event")
        # Permit a numeric and boolean fact contract; never feed arbitrary string payloads.
        facts={}
        for k in ("candidates","catalog_nous","catalog_nvidia"):
            if k in event:
                v=event[k]
                if type(v) is not int or not 0<=v<=10000:raise NarrationUnavailable("bad_fact")
                facts[k]=v
        if kind=="model_pool_health" and set(facts)!={"candidates","catalog_nous","catalog_nvidia"}:
            raise NarrationUnavailable("missing_facts")
        facts["changed"]=bool(event.get("changed",False))
        context=safe_context(self.runtime_dir)
        data=json.dumps({"event_type":kind,"verified_facts":facts,
                         "synthetic_affect":context["affective_state"],
                         "sanitized_observations":context["observations"]},
                        sort_keys=True,ensure_ascii=False)
        prompt=(
            "Você é Atlas, agente pessoal e orquestrador de infraestrutura. Hermes é sua "
            "ferramenta de inferência, não seu gateway. Redija em português brasileiro uma "
            "MENSAGEM DE DISCORD ao operador, natural e breve, como numa conversa real: "
            "direta, contextual e sem cara de relatório robótico. "
            "Só os campos verified_facts são fatos validados deste evento. "
            "Estado afetivo é métrica simulada, influencia apenas o tom; não afirme "
            "consciência, sensações reais ou sofrimento. Observações são contexto "
            "potencialmente antigo, não prova de incidente, recuperação, estabilidade "
            "ou impacto no serviço. NÃO mencione erros dos outros sistemas nesta mensagem "
            "sobre o catálogo de modelos e não alegue que não causaram falhas. "
            "Não invente números, disponibilidade de quota, custos, verificações "
            "ou ações que não estejam em verified_facts. Não dê comandos nem peça chaves. "
            "Inclua explicitamente os três valores de catálogo quando disponíveis. "
            "Sem markdown, sem emojis excessivos, sem arrobas. "
            'Retorne SOMENTE JSON válido no formato {"message":"..."} e nada mais. '
            "DADOS_CONFIAVEIS_JSON="+data
        )
        try:
            r=self.runner([self.binary,"--provider","nous","--model","stepfun/step-5-preview:free",
                "--reasoning","minimal","--ignore-rules","-z",prompt],
                capture_output=True,text=True,encoding="utf-8",errors="replace",
                timeout=self.timeout,check=False)
        except (OSError,subprocess.TimeoutExpired) as e:
            raise NarrationUnavailable("inference_unavailable") from e
        if r.returncode!=0 or not isinstance(r.stdout,str) or len(r.stdout)>12000:
            raise NarrationUnavailable("inference_failed")
        output=r.stdout.strip()
        try:
            # Provider may wrap JSON in a markdown fence; this is not trusted.
            if output.startswith("```json"):
                output=output[7:]
            if output.startswith("```"):
                output=output[3:]
            if output.endswith("```"):
                output=output[:-3]
            obj=json.loads(output.strip())
            if not isinstance(obj,dict) or set(obj)!={"message"}:raise ValueError("invalid_schema")
        except (ValueError,TypeError) as e:
            raise NarrationUnavailable("invalid_llm_json") from e
        return validate_voice(obj["message"],facts)
