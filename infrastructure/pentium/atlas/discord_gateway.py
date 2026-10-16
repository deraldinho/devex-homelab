from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .chat_inbox import ChatInbox
from .config_discord import DiscordConfig, load_discord_config
from .discord_notification_format import format_atlas_alert

ROOT=Path(__file__).resolve().parent
STATE_DIR=Path.home()/"pentium-agent"/"atlas"/"runtime"


class DiscordGatewayHealthStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def write(self, state: str, *, latency_s: float | None = None, reason: str | None = None) -> dict:
        state = str(state or "unknown").strip().lower() or "unknown"
        payload = {"schema_version": 1, "state": state, "connected": state == "connected",
                   "reason": reason, "latency_s": latency_s,
                   "updated_at": datetime.now(timezone.utc).isoformat()}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, self.path)
        return payload


async def publish_online_presence(client, discord_module) -> None:
    await client.change_presence(status=discord_module.Status.online,
                                 activity=discord_module.Game(name="Atlas • homelab online"))


@dataclass(frozen=True)
class DiscordReply:
    event_id: int
    reply_target: str
    message: str
    client_message_id: str | None = None


def split_discord_message(content: str, max_chars: int = 1900) -> list[str]:
    text = str(content or "").strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks = []
    lines = text.split("\n")
    current_chunk = []
    current_len = 0
    in_code_block = False
    code_lang = ""

    for line in lines:
        stripped = line.strip()
        is_code_fence = stripped.startswith("```")
        if is_code_fence:
            if not in_code_block:
                in_code_block = True
                code_lang = stripped[3:].strip()
            else:
                in_code_block = False
                code_lang = ""

        line_len = len(line) + 1
        if current_len + line_len > max_chars and current_chunk:
            if in_code_block:
                current_chunk.append("```")
            chunks.append("\n".join(current_chunk).strip())
            current_chunk = []
            if in_code_block:
                current_chunk.append(f"```{code_lang}")
                current_len = len(current_chunk[0]) + 1
            else:
                current_len = 0

        current_chunk.append(line)
        current_len += line_len

    if current_chunk:
        chunks.append("\n".join(current_chunk).strip())

    return [c for c in chunks if c]


class DiscordEventReader:
    def __init__(self,path:Path,*,max_events:int=128):
        self.path=Path(path); self.max_events=max(1,int(max_events))

    def after(self,last_event_id:int)->tuple[DiscordReply,...]:
        if not self.path.is_file(): return ()
        replies=[]
        for line in self.path.read_text(encoding="utf-8").splitlines()[-self.max_events:]:
            try: event=json.loads(line)
            except json.JSONDecodeError: continue
            if not isinstance(event,dict) or int(event.get("id",0))<=int(last_event_id): continue
            payload=event.get("payload") or {}
            if event.get("type")!="chat_message" or payload.get("role")!="atlas" or payload.get("channel")!="discord": continue
            target=str(payload.get("reply_target") or "").strip(); message=str(payload.get("message") or "").strip()
            client_msg_id=str(payload.get("client_message_id") or "").strip() or None
            if target and message:
                replies.append(DiscordReply(int(event["id"]),target,message,client_msg_id))
        return tuple(replies)


class DiscordReplyCursor:
    def __init__(self,path:Path): self.path=Path(path)
    def load(self)->int:
        if not self.path.is_file(): return 0
        try: payload=json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError,json.JSONDecodeError): return 0
        value=payload.get("last_event_id",0) if isinstance(payload,dict) else 0
        return max(0,int(value))
    def save(self,event_id:int)->None:
        value=max(0,int(event_id));self.path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_name(self.path.name+".tmp")
        try:
            tmp.write_text(json.dumps({"schema_version":1,"last_event_id":value},sort_keys=True)+"\n",encoding="utf-8")
            os.replace(tmp,self.path)
        finally: tmp.unlink(missing_ok=True)


class DiscordChatBridge:
    def __init__(self,config:DiscordConfig,inbox:ChatInbox,event_reader:DiscordEventReader):
        self.config=config;self.inbox=inbox;self.event_reader=event_reader

    def accept_message(self,message_id:str,content:str,*,guild_id:str,channel_id:str,user_id:str,user_name:str="",is_bot:bool=False):
        if is_bot or not self.config.accepts(guild_id=str(guild_id),channel_id=str(channel_id),user_id=str(user_id)):
            return None
        text=str(content).strip()
        if user_name:
            prefix = f"{user_name}: "
            if not text.startswith(prefix):
                text = f"{prefix}{text}"
        if not text or len(text)>self.config.max_message_chars:
            return None
        return self.inbox.enqueue(
            text,f"discord:{message_id}",channel="discord",actor_id=str(user_id),
            conversation_id=str(channel_id),reply_target=str(channel_id),
        )

    def responses_after(self,last_event_id:int)->tuple[DiscordReply,...]:
        return self.event_reader.after(last_event_id)


def resolve_discord_activation(config: DiscordConfig, env=None) -> str:
    values=os.environ if env is None else env
    if not config.enabled:
        raise RuntimeError("discord gateway disabled")
    token=str(values.get("ATLAS_DISCORD_BOT_TOKEN","")).strip()
    if not token:
        raise RuntimeError("discord bot token unavailable")
    if not config.guild_ids or not config.channel_ids or not config.user_ids:
        raise RuntimeError("discord allowlists are incomplete")
    return token


def _resolve_channel(guild, ref: str):
    if not guild or not ref:
        return None
    cleaned = str(ref).strip().lstrip("<#").rstrip(">")
    if cleaned.isdigit() and hasattr(guild, "get_channel"):
        try:
            ch = guild.get_channel(int(cleaned))
            if ch is not None:
                return ch
        except Exception:
            pass
    for c in getattr(guild, "text_channels", ()):
        c_name = getattr(c, "name", "")
        c_id = getattr(c, "id", "")
        if str(c_name).lower() == cleaned.lower() or str(c_id) == cleaned:
            return c
    return None


class DiscordConfirmationManager:
    def __init__(self, timeout_s: float = 15.0):
        import time
        self.timeout_s = float(timeout_s)
        self._time = time.monotonic
        self._pending: dict[tuple[str, str], tuple[object, str, float]] = {}

    def request(self, guild_id: str, user_id: str, description: str, callback) -> str:
        key = (str(guild_id), str(user_id))
        self._pending[key] = (callback, description, self._time())
        return (
            f"⚠️ **Confirmação Requerida (15s):** Deseja realmente {description}?\n"
            "Digite `!confirmar` nos próximos 15 segundos para executar."
        )

    async def confirm(self, guild_id: str, user_id: str) -> tuple[bool, str]:
        key = (str(guild_id), str(user_id))
        item = self._pending.pop(key, None)
        if not item:
            return False, "❌ Nenhuma ação pendente de confirmação."
        callback, description, timestamp = item
        if (self._time() - timestamp) > self.timeout_s:
            return False, "⏱️ Tempo limite de confirmação expirado (15s). Ação cancelada por segurança."
        await callback()
        return True, f"✅ Ação executada com sucesso: {description}."


GLOBAL_CONFIRMATION_MANAGER = DiscordConfirmationManager(timeout_s=15.0)


async def create_incident_channel(guild, slug: str, *, topic: str = ""):
    if not guild or not hasattr(guild, "create_text_channel"):
        return None
    name = f"🚨-incidente-{slug.lower().replace(' ', '-')}"
    ch = await guild.create_text_channel(name, topic=topic or f"Canal de resposta a incidentes: {slug}")
    return ch


async def resolve_incident_channel(guild, ch_ref: str, *, post_mortem: str = ""):
    ch = _resolve_channel(guild, ch_ref)
    if not ch or not hasattr(ch, "edit"):
        return None
    curr_name = str(getattr(ch, "name", "") or "")
    if curr_name.startswith("🚨-"):
        curr_name = curr_name[len("🚨-"):]
    if curr_name.startswith("incidente-"):
        curr_name = curr_name[len("incidente-"):]
    new_name = f"✅-resolvido-{curr_name}"
    await ch.edit(name=new_name)
    if post_mortem and hasattr(ch, "send"):
        await ch.send(f"📋 **Post-Mortem do Incidente:**\n{post_mortem}")
    return ch


def record_passive_chat_memory(state_dir: Path, message) -> None:
    import time
    path = Path(state_dir) / "passive-chat-memories.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    author = getattr(message, "author", None)
    entry = {
        "timestamp": time.time(),
        "guild_id": str(getattr(getattr(message, "guild", None), "id", "") or ""),
        "channel_id": str(getattr(getattr(message, "channel", None), "id", "") or ""),
        "message_id": str(getattr(message, "id", "") or ""),
        "user_id": str(getattr(author, "id", "") or ""),
        "user_name": str(getattr(author, "display_name", "") or getattr(author, "name", "") or ""),
        "content": str(getattr(message, "content", "") or ""),
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def should_respond_actively(message, client, config: DiscordConfig) -> bool:
    ch_id = str(getattr(getattr(message, "channel", None), "id", "") or "")
    if config.console_channel_id and ch_id == str(config.console_channel_id):
        return True
    client_user = getattr(client, "user", None)
    if client_user and hasattr(message, "mentions") and client_user in message.mentions:
        return True
    content = str(getattr(message, "content", "") or "").lower()
    if "@devexmachina" in content or "atlas" in content:
        return True
    ref = getattr(message, "reference", None)
    if ref and getattr(ref, "resolved", None):
        ref_author = getattr(ref.resolved, "author", None)
        if client_user and ref_author and str(getattr(ref_author, "id", None)) == str(getattr(client_user, "id", None)):
            return True
    return False


def _canonical_service_states(state_dir: Path) -> dict[str, str] | None:
    path = Path(state_dir) / "health-supervisor.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        return None
    components = payload.get("components")
    if not isinstance(components, list):
        return None
    states: dict[str, str] = {}
    for item in components:
        if not isinstance(item, dict):
            continue
        component_id = str(item.get("component_id") or "").strip()
        state = str(item.get("state") or "").strip().lower()
        if component_id and state:
            states[component_id] = state
    return states or None


def format_system_dashboard(*, state_dir: Path = STATE_DIR, systemctl_runner=None) -> str:
    import datetime
    import shutil
    import subprocess
    if systemctl_runner is None:
        systemctl_runner = subprocess.run
    now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    disk_str = "N/A"
    try:
        total, used, free = shutil.disk_usage(Path.home())
        disk_pct = int(used / total * 100)
        disk_str = f"{used // (1024**3)}GB / {total // (1024**3)}GB ({disk_pct}%)"
    except Exception:
        pass

    mem_str = "N/A"
    try:
        meminfo = Path("/proc/meminfo")
        if meminfo.is_file():
            data = {}
            for line in meminfo.read_text(encoding="utf-8").splitlines()[:6]:
                parts = line.split(":")
                if len(parts) == 2:
                    data[parts[0].strip()] = int(parts[1].split()[0])
            total_kb = data.get("MemTotal", 0)
            avail_kb = data.get("MemAvailable", 0)
            if total_kb:
                used_kb = total_kb - avail_kb
                mem_pct = int(used_kb / total_kb * 100)
                mem_str = f"{used_kb // 1024}MB / {total_kb // 1024}MB ({mem_pct}%)"
    except Exception:
        pass

    load_str = "N/A"
    try:
        load = os.getloadavg()
        load_str = f"{load[0]:.2f}, {load[1]:.2f}, {load[2]:.2f}"
    except Exception:
        pass

    canonical_states = _canonical_service_states(Path(state_dir))
    srv_status = []
    if canonical_states is not None:
        services = [
            "atlas-cognitive.service",
            "atlas-discord.service",
            "atlas-observation.service",
            "atlas-dashboard.service",
            "atlas-voice.service",
        ]
        icons = {
            "healthy": "🟢",
            "paused_intentionally": "⏸️",
            "recovering": "🟡",
            "degraded": "🟠",
            "stale": "🟠",
            "disconnected": "🔴",
            "failed": "🔴",
            "unknown": "⚪",
        }
        for srv in services:
            st = canonical_states.get(srv, "unknown")
            srv_status.append(f"{icons.get(st, '⚪')} `{srv}`: {st}")
    else:
        services = ["atlas-cognitive.service", "atlas-discord.service", "atlas-observation.service"]
        for srv in services:
            try:
                res = systemctl_runner(["systemctl", "--user", "is-active", srv], capture_output=True, text=True, timeout=2)
                st = res.stdout.strip()
                icon = "🟢" if st == "active" else "🔴"
                srv_status.append(f"{icon} `{srv}`: {st}")
            except Exception:
                srv_status.append(f"⚪ `{srv}`: running")

    return (
        "📌 **[ATLAS LIVE DASHBOARD]**\n"
        f"🕒 *Atualizado em:* `{now_utc}`\n\n"
        "💻 **Nó Pentium (Cognitive & Control):**\n"
        f"• **CPU Load:** `{load_str}`\n"
        f"• **Memória:** `{mem_str}`\n"
        f"• **Disco:** `{disk_str}`\n\n"
        "⚙️ **Serviços Ativos:**\n" +
        "\n".join(srv_status) +
        "\n\n🟢 *Hermes local 100% isolado no Pentium.*"
    )


def format_watchdog_dashboard(l2j_data: dict) -> str:
    import datetime
    now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    
    probes = l2j_data.get("probes", {}) if isinstance(l2j_data, dict) else {}
    services = probes.get("services", {}) if isinstance(probes, dict) else {}
    jvm = l2j_data.get("jvm", {}) if isinstance(l2j_data, dict) else {}
    docker = l2j_data.get("docker", {}) if isinstance(l2j_data, dict) else {}
    
    gs_up = services.get("gameserver_tcp", {}).get("reachable", False)
    login_up = services.get("loginserver_tcp", {}).get("reachable", False)
    db_up = services.get("database_mariadb", {}).get("reachable", False)
    prom_up = services.get("prometheus_http", {}).get("reachable", False)
    graf_up = services.get("grafana_http", {}).get("reachable", False)
    
    gs_icon = "🟢 UP" if gs_up else "🔴 DOWN"
    login_icon = "🟢 UP" if login_up else "🔴 DOWN"
    db_icon = "🟢 UP" if db_up else "🔴 DOWN"
    prom_icon = "🟢 UP" if prom_up else "⚪ N/A"
    graf_icon = "🟢 UP (6 dashboards)" if graf_up else "⚪ N/A"
    
    total_containers = docker.get("total_containers_found", 0)
    container_icon = "🟢" if total_containers >= 7 else ("🟡" if total_containers > 0 else "🔴")
    
    heap_used = jvm.get("heap_used_mb")
    heap_comm = jvm.get("heap_committed_mb")
    heap_pct = jvm.get("heap_usage_pct")
    heap_warning = l2j_data.get("heap_warning", False)
    
    if heap_used is not None and heap_comm is not None:
        heap_icon = "⚠️" if heap_warning else "🟢"
        heap_str = f"{heap_icon} `{heap_used}MB / {heap_comm}MB` ({heap_pct}%)"
        if heap_warning:
            heap_str += " — **Alerta: Heap ≥ 90%**"
    else:
        heap_str = "⚪ Telemetria Prometheus indisponível"
        
    threads = jvm.get("jvm_threads_current")
    threads_str = f"{int(threads)}" if threads is not None else "N/A"
    cpu = jvm.get("process_cpu_pct")
    cpu_str = f"{cpu}%" if cpu is not None else "N/A"
    
    overall = probes.get("overall_status", "UNKNOWN")
    status_icon = "🟢 OPERACIONAL" if overall == "HEALTHY" else ("🟡 DEGRADADO" if overall == "DEGRADED" else "🔴 CRÍTICO")
    
    return (
        "🛡️ **[ATLAS PROACTIVE WATCHDOG — L2JTOREN & CLUSTER HEALTH]**\n"
        f"🕒 *Verificação Contínua:* `{now_utc}` | Status: **{status_icon}**\n\n"
        "🎮 **Serviços Lineage 2 / L2jToren (Nó x99 - `100.101.23.111`):**\n"
        f"• **GameServer (Porta 7777 TCP):** {gs_icon}\n"
        f"• **LoginServer (Porta 2106 TCP):** {login_icon}\n"
        f"• **MariaDB (Porta 3306 TCP):** {db_icon}\n"
        f"• **Prometheus / Grafana:** {prom_icon} | {graf_icon}\n"
        f"• **Containers Docker:** {container_icon} `{total_containers}` containers ativos\n\n"
        "📊 **Telemetria de Performance JVM (GameServer):**\n"
        f"• **Memória Heap:** {heap_str}\n"
        f"• **Threads Ativas:** `{threads_str}` | **Carga de CPU:** `{cpu_str}`\n\n"
        "🩺 **Vigilância Biomecânica Contínua:**\n"
        "• **Sondas Ativas:** Socket TCP instantâneo + Métricas Prometheus + Docker status via SSH\n"
        "• **Política de Alertas:** Notificação proativa imediata em caso de queda de portas vitais ou Heap ≥ 90%."
    )


async def run_live_watchdog(client, config: DiscordConfig, state_dir: Path = STATE_DIR):
    target_channel_id = config.alert_channel_id or config.console_channel_id
    if not target_channel_id:
        return
    state_dir = Path(state_dir)
    msg_id_file = state_dir / "watchdog-board-msg-id.json"
    
    try:
        from .l2j_observation import L2jObservationService
        l2j_svc = L2jObservationService()
    except Exception:
        return

    last_probe_states: dict[str, bool] = {}
    last_heap_alert_time: float = 0.0

    while not client.is_closed():
        try:
            ch_id = int(target_channel_id)
            channel = client.get_channel(ch_id)
            if channel is None and hasattr(client, "fetch_channel"):
                channel = await client.fetch_channel(ch_id)

            if channel is not None and hasattr(channel, "send"):
                loop = asyncio.get_running_loop()
                l2j_data = await loop.run_in_executor(None, l2j_svc.get_summary)
                
                # 1. Alertas de transição de portas críticas
                probes = l2j_data.get("probes", {}) if isinstance(l2j_data, dict) else {}
                services = probes.get("services", {}) if isinstance(probes, dict) else {}
                critical_keys = [
                    ("gameserver_tcp", "GameServer (7777 TCP)"),
                    ("loginserver_tcp", "LoginServer (2106 TCP)"),
                    ("database_mariadb", "MariaDB (3306 TCP)")
                ]
                
                for srv_key, srv_name in critical_keys:
                    curr_up = services.get(srv_key, {}).get("reachable", False)
                    prev_up = last_probe_states.get(srv_key)
                    if prev_up is not None:
                        if prev_up and not curr_up:
                            await channel.send(f"🚨 **[WATCHDOG ALERTA CRÍTICO]** O serviço **{srv_name}** no nó x99 caiu ou ficou inacessível!")
                        elif not prev_up and curr_up:
                            await channel.send(f"✅ **[WATCHDOG RECUPERAÇÃO]** O serviço **{srv_name}** no nó x99 foi normalizado e voltou a responder!")
                    last_probe_states[srv_key] = curr_up

                # 2. Alerta de JVM Heap (cooldown de 30 minutos)
                import time
                heap_warning = l2j_data.get("heap_warning", False)
                now_ts = time.time()
                if heap_warning and (now_ts - last_heap_alert_time > 1800):
                    jvm = l2j_data.get("jvm", {}) if isinstance(l2j_data, dict) else {}
                    pct = jvm.get("heap_usage_pct", "?")
                    used = jvm.get("heap_used_mb", "?")
                    comm = jvm.get("heap_committed_mb", "?")
                    await channel.send(
                        f"⚠️ **[WATCHDOG ALERTA DE HEAP]** O GameServer está com ocupação de memória Heap crítica: **{pct}%** ({used}MB / {comm}MB)!\n"
                        f"Risco iminente de degradação de garbage collection ou indisponibilidade do jogo."
                    )
                    last_heap_alert_time = now_ts

                # 3. Painel fixo/pinado no canal do watchdog
                board_text = format_watchdog_dashboard(l2j_data)
                target_msg = None
                if msg_id_file.is_file():
                    try:
                        saved = json.loads(msg_id_file.read_text(encoding="utf-8"))
                        saved_id = saved.get("message_id")
                        if saved_id and hasattr(channel, "fetch_message"):
                            target_msg = await channel.fetch_message(int(saved_id))
                    except Exception:
                        target_msg = None

                if target_msg is not None and hasattr(target_msg, "edit"):
                    await target_msg.edit(content=board_text)
                else:
                    new_msg = await channel.send(board_text)
                    if hasattr(new_msg, "pin"):
                        try: await new_msg.pin()
                        except Exception: pass
                    msg_id_file.write_text(json.dumps({"message_id": getattr(new_msg, "id", 0)}) + "\n", encoding="utf-8")
        except Exception:
            pass

        await asyncio.sleep(45.0)


async def run_live_dashboard(client, config: DiscordConfig, state_dir: Path = STATE_DIR):
    if not config.console_channel_id:
        return
    state_dir = Path(state_dir)
    msg_id_file = state_dir / "dashboard-msg-id.json"

    while not client.is_closed():
        try:
            ch_id = int(config.console_channel_id)
            channel = client.get_channel(ch_id)
            if channel is None and hasattr(client, "fetch_channel"):
                channel = await client.fetch_channel(ch_id)

            if channel is not None and hasattr(channel, "send"):
                dashboard_text = format_system_dashboard()
                target_msg = None

                if msg_id_file.is_file():
                    try:
                        saved = json.loads(msg_id_file.read_text(encoding="utf-8"))
                        saved_id = saved.get("message_id")
                        if saved_id and hasattr(channel, "fetch_message"):
                            target_msg = await channel.fetch_message(int(saved_id))
                    except Exception:
                        target_msg = None

                if target_msg is not None and hasattr(target_msg, "edit"):
                    await target_msg.edit(content=dashboard_text)
                else:
                    new_msg = await channel.send(dashboard_text)
                    if hasattr(new_msg, "pin"):
                        try:
                            await new_msg.pin()
                        except Exception:
                            pass
                    msg_id_file.write_text(json.dumps({"message_id": getattr(new_msg, "id", 0)}) + "\n", encoding="utf-8")
        except Exception:
            pass

        await asyncio.sleep(config.dashboard_update_interval_s)


async def _safe_delete(msg):
    if msg is not None and hasattr(msg, "delete"):
        try:
            res = msg.delete()
            if asyncio.iscoroutine(res):
                await res
        except Exception:
            pass


async def handle_control_command(message, client, config: DiscordConfig, confirmation_mgr: DiscordConfirmationManager | None = None) -> bool:
    if confirmation_mgr is None:
        confirmation_mgr = GLOBAL_CONFIRMATION_MANAGER

    content = str(getattr(message, "content", "") or "").strip()
    if not content.startswith("!"):
        return False

    channel = getattr(message, "channel", None)
    guild = getattr(message, "guild", None)
    author = getattr(message, "author", None)
    author_id = str(getattr(author, "id", "") or "")

    if not config.is_admin(author_id):
        if channel is not None and hasattr(channel, "send"):
            await channel.send("⛔ Acesso negado. Apenas operadores autorizados podem gerenciar canais e mensagens.")
        return True

    parts = content[1:].split()
    if not parts:
        return False
    cmd = parts[0].lower()
    args = parts[1:]

    # 1. Comandos de Confirmação de 2 Etapas
    if cmd in {"confirmar", "confirm"}:
        success, msg_text = await confirmation_mgr.confirm(str(getattr(guild, "id", "")), author_id)
        if channel is not None and hasattr(channel, "send"):
            await channel.send(msg_text)
        return True

    # 2. Comandos de Canal
    elif cmd == "canal":
        if not args:
            await channel.send(
                "ℹ️ **Uso de Canais:**\n"
                "• `!canal criar <nome> [topico]`\n"
                "• `!canal renomear <#canal|id|nome> <novo_nome>`\n"
                "• `!canal topico <#canal|id|nome> <topico>`\n"
                "• `!canal excluir <#canal|id|nome>` (requer `!confirmar`)\n"
                "• `!canal listar`"
            )
            return True
        sub = args[0].lower()

        if sub == "criar" and len(args) >= 2:
            name = args[1].lower().replace(" ", "-")
            topic = " ".join(args[2:]) if len(args) > 2 else ""
            if guild is not None and hasattr(guild, "create_text_channel"):
                new_ch = await guild.create_text_channel(name, topic=topic)
                mention = getattr(new_ch, "mention", f"#{name}")
                await channel.send(f"✅ Canal criado com sucesso: {mention} (ID: `{new_ch.id}`)")
            return True

        elif sub == "renomear" and len(args) >= 3:
            target_ref, new_name = args[1], args[2].lower().replace(" ", "-")
            target_ch = _resolve_channel(guild, target_ref)
            if target_ch and hasattr(target_ch, "edit"):
                old_name = target_ch.name
                await target_ch.edit(name=new_name)
                mention = getattr(target_ch, "mention", f"#{new_name}")
                await channel.send(f"✅ Canal `#{old_name}` renomeado para `#{new_name}` ({mention})")
            else:
                await channel.send(f"❌ Canal `{target_ref}` não encontrado.")
            return True

        elif sub == "topico" and len(args) >= 3:
            target_ref = args[1]
            new_topic = " ".join(args[2:])
            target_ch = _resolve_channel(guild, target_ref)
            if target_ch and hasattr(target_ch, "edit"):
                await target_ch.edit(topic=new_topic)
                mention = getattr(target_ch, "mention", f"#{target_ch.name}")
                await channel.send(f"✅ Tópico do canal {mention} atualizado!")
            else:
                await channel.send(f"❌ Canal `{target_ref}` não encontrado.")
            return True

        elif sub == "excluir" and len(args) >= 2:
            target_ref = args[1]
            target_ch = _resolve_channel(guild, target_ref)
            if target_ch and hasattr(target_ch, "delete"):
                protected = {
                    str(config.alert_channel_id or ""),
                    str(config.memory_channel_id or ""),
                    str(config.notes_channel_id or ""),
                    str(config.console_channel_id or ""),
                }
                if str(target_ch.id) in protected:
                    mention = getattr(target_ch, "mention", f"#{target_ch.name}")
                    await channel.send(f"🛡️ O canal {mention} é protegido pela governança do Homelab e não pode ser excluído.")
                    return True

                ch_name = target_ch.name
                async def do_delete():
                    await target_ch.delete()
                    if channel is not None and hasattr(channel, "send"):
                        await channel.send(f"🗑️ Canal `#{ch_name}` excluído com sucesso.")

                prompt = confirmation_mgr.request(
                    str(getattr(guild, "id", "")), author_id,
                    f"excluir o canal `#{ch_name}`", do_delete
                )
                await channel.send(prompt)
            else:
                await channel.send(f"❌ Canal `{target_ref}` não encontrado.")
            return True

        elif sub == "listar":
            if guild is not None:
                channels_info = [
                    f"• {getattr(c, 'mention', f'#{c.name}')} (`{c.id}`)"
                    for c in getattr(guild, "text_channels", ())
                ]
                await channel.send("📋 **Canais de Texto no Servidor:**\n" + "\n".join(channels_info))
            return True

    # 3. Comandos de Mensagem
    elif cmd == "msg":
        if not args:
            await channel.send(
                "ℹ️ **Uso de Mensagens:**\n"
                "• `!msg excluir [id_msg]` (ou responda a ela)\n"
                "• `!msg editar <id_msg> <novo_texto>` (apenas mensagens do bot)\n"
                "• `!msg fixar [id_msg]`\n"
                "• `!msg desfixar [id_msg]`"
            )
            return True
        sub = args[0].lower()

        ref_msg = getattr(message, "reference", None)
        target_msg_id = None
        if ref_msg and getattr(ref_msg, "message_id", None):
            target_msg_id = ref_msg.message_id
        elif len(args) >= 2 and args[1].isdigit():
            target_msg_id = int(args[1])

        if sub == "excluir":
            if target_msg_id and channel is not None and hasattr(channel, "fetch_message"):
                try:
                    target_msg = await channel.fetch_message(target_msg_id)
                    await _safe_delete(target_msg)
                    await _safe_delete(message)
                except Exception as exc:
                    await channel.send(f"❌ Falha ao excluir mensagem: {exc}")
            else:
                await channel.send("❌ Informe o ID da mensagem ou responda à mensagem desejada com `!msg excluir`.")
            return True

        elif sub == "editar" and len(args) >= 3:
            msg_id = int(args[1]) if args[1].isdigit() else target_msg_id
            new_text = " ".join(args[2:]) if args[1].isdigit() else " ".join(args[1:])
            if msg_id and channel is not None and hasattr(channel, "fetch_message"):
                try:
                    target_msg = await channel.fetch_message(msg_id)
                    client_user = getattr(client, "user", None)
                    target_author_id = str(getattr(getattr(target_msg, "author", None), "id", "") or "")
                    client_id = str(getattr(client_user, "id", "") or "")
                    if client_id and target_author_id and target_author_id != client_id:
                        await channel.send("❌ Discord não permite editar mensagens de outros usuários. Você só pode editar mensagens enviadas pelo próprio bot.")
                        return True
                    if hasattr(target_msg, "edit"):
                        res = target_msg.edit(content=new_text)
                        if asyncio.iscoroutine(res):
                            await res
                    await _safe_delete(message)
                    await channel.send("✅ Mensagem editada com sucesso.")
                except Exception as exc:
                    await channel.send(f"❌ Falha ao editar mensagem: {exc}")
            return True

        elif sub in {"fixar", "pin"}:
            if target_msg_id and channel is not None and hasattr(channel, "fetch_message"):
                try:
                    target_msg = await channel.fetch_message(target_msg_id)
                    if hasattr(target_msg, "pin"):
                        res = target_msg.pin()
                        if asyncio.iscoroutine(res):
                            await res
                    await _safe_delete(message)
                except Exception as exc:
                    await channel.send(f"❌ Falha ao fixar mensagem: {exc}")
            return True

        elif sub in {"desfixar", "unpin"}:
            if target_msg_id and channel is not None and hasattr(channel, "fetch_message"):
                try:
                    target_msg = await channel.fetch_message(target_msg_id)
                    if hasattr(target_msg, "unpin"):
                        res = target_msg.unpin()
                        if asyncio.iscoroutine(res):
                            await res
                    await _safe_delete(message)
                except Exception as exc:
                    await channel.send(f"❌ Falha ao desfixar mensagem: {exc}")
            return True

    # 4. Limpeza de Mensagens (com confirmação para > 20)
    elif cmd in {"limpar", "purge", "clear"}:
        qty = 10
        if args and args[0].isdigit():
            qty = min(100, max(1, int(args[0])))
        if channel is not None and hasattr(channel, "purge"):
            if qty > 20:
                async def do_purge():
                    deleted = await channel.purge(limit=qty + 1)
                    confirm = await channel.send(f"🧹 Limpeza concluída: {max(0, len(deleted) - 1)} mensagens removidas.")
                    await asyncio.sleep(4)
                    if hasattr(confirm, "delete"):
                        try: await confirm.delete()
                        except Exception: pass

                prompt = confirmation_mgr.request(
                    str(getattr(guild, "id", "")), author_id,
                    f"expurgar {qty} mensagens do canal", do_purge
                )
                await channel.send(prompt)
                return True
            else:
                deleted = await channel.purge(limit=qty + 1)
                confirm = await channel.send(f"🧹 Limpeza concluída: {max(0, len(deleted) - 1)} mensagens removidas.")
                await asyncio.sleep(4)
                if hasattr(confirm, "delete"):
                    try: await confirm.delete()
                    except Exception: pass
        return True

    # 5. Ajuda Operacional
    elif cmd in {"ajuda", "help"}:
        help_text = (
            "🤖 **Controle Operacional do Atlas no Discord**\n\n"
            "**Gestão de Canais:**\n"
            "• `!canal criar <nome> [topico]` — Cria um novo canal de texto\n"
            "• `!canal renomear <#canal|id|nome> <novo_nome>` — Renomeia um canal existente\n"
            "• `!canal topico <#canal|id|nome> <novo_topico>` — Altera o tópico/descrição\n"
            "• `!canal excluir <#canal|id|nome>` — Exclui um canal (requer confirmação `!confirmar`)\n"
            "• `!canal listar` — Lista todos os canais de texto do servidor\n\n"
            "**Gestão de Mensagens:**\n"
            "• `!msg excluir [id_msg]` — Exclui a mensagem (ou responda a ela)\n"
            "• `!msg editar <id_msg> <novo_conteudo>` — Edita mensagem enviada pelo bot\n"
            "• `!msg fixar [id_msg]` / `!msg desfixar [id_msg]` — Fixa ou desafixa mensagens\n"
            "• `!limpar [quantidade]` — Expurga mensagens (se > 20, requer `!confirmar`)\n"
            "• `!confirmar` — Executa comando destrutivo pendente (janela de 15s)\n"
        )
        await channel.send(help_text)
        return True

    return False


async def _run_discord_client(config: DiscordConfig, token: str, *, state_dir: Path = STATE_DIR):
    try:
        import discord
    except ImportError as exc:
        raise RuntimeError("discord.py unavailable") from exc
    state_dir=Path(state_dir)
    inbox=ChatInbox(state_dir/"chat-inbox.json",max_items=32,max_message_chars=config.max_message_chars)
    reader=DiscordEventReader(state_dir/"dashboard-events.jsonl")
    bridge=DiscordChatBridge(config,inbox,reader)
    cursor=DiscordReplyCursor(state_dir/"discord-cursor.json")
    intents=discord.Intents.default(); intents.message_content=True
    client=discord.Client(intents=intents)
    gateway_health=DiscordGatewayHealthStore(state_dir/"discord-gateway-health.json")
    gateway_health.write("starting", reason="client_start")
    pump_task=None
    dashboard_task=None
    actions_task=None
    watchdog_task=None

    async def pump_replies():
        while not client.is_closed():
            for reply in bridge.responses_after(cursor.load()):
                try:
                    channel=client.get_channel(int(reply.reply_target))
                    if channel is None: channel=await client.fetch_channel(int(reply.reply_target))
                    chunks = split_discord_message(reply.message, max_chars=1900)
                    msg_ref = None
                    if reply.client_message_id and str(reply.client_message_id).startswith("discord:"):
                        raw_id = str(reply.client_message_id).split(":", 1)[-1].strip()
                        if raw_id.isdigit():
                            try:
                                import discord
                                msg_ref = discord.MessageReference(message_id=int(raw_id), channel_id=channel.id)
                            except Exception:
                                msg_ref = None
                    for idx, chunk in enumerate(chunks):
                        ref = msg_ref if idx == 0 else None
                        try:
                            if ref is not None:
                                await channel.send(chunk, reference=ref, mention_author=False)
                            else:
                                await channel.send(chunk)
                        except Exception:
                            await channel.send(chunk)
                except Exception:
                    break
                cursor.save(reply.event_id)
            await asyncio.sleep(config.poll_interval_s)

    async def pump_actions():
        action_cursor_file = state_dir / "discord-action-cursor.json"
        queue_file = state_dir / "discord-action-queue.jsonl"
        last_seen = 0
        if action_cursor_file.is_file():
            try:
                last_seen = int(json.loads(action_cursor_file.read_text(encoding="utf-8")).get("last_seen", 0))
            except Exception:
                last_seen = 0

        while not client.is_closed():
            if queue_file.is_file():
                try:
                    lines = queue_file.read_text(encoding="utf-8").splitlines()
                    if len(lines) > last_seen:
                        for line in lines[last_seen:]:
                            try:
                                item = json.loads(line)
                                cap = str(item.get("capability") or "")
                                args = dict(item.get("arguments") or {})
                                guild = client.get_guild(int(config.guild_ids[0])) if config.guild_ids else None

                                if cap == "discord_create_channel" and guild:
                                    name = str(args.get("name") or "novo-canal").lower().replace(" ", "-")
                                    topic = str(args.get("topic") or "")
                                    new_ch = await guild.create_text_channel(name, topic=topic)
                                    if config.console_channel_id:
                                        c = client.get_channel(int(config.console_channel_id))
                                        if c: await c.send(f"🤖 **[HERMES AÇÃO]** Canal criado: {new_ch.mention}")

                                elif cap == "discord_rename_channel" and guild:
                                    ch_ref = str(args.get("channel") or "")
                                    new_name = str(args.get("new_name") or "").lower().replace(" ", "-")
                                    ch = _resolve_channel(guild, ch_ref)
                                    if ch and hasattr(ch, "edit"):
                                        old_name = ch.name
                                        await ch.edit(name=new_name)
                                        if config.console_channel_id:
                                            c = client.get_channel(int(config.console_channel_id))
                                            if c: await c.send(f"🤖 **[HERMES AÇÃO]** Canal `#{old_name}` renomeado para `#{new_name}`.")

                                elif cap == "discord_send_alert":
                                    target = args.get("channel") or config.alert_channel_id
                                    msg_txt = str(args.get("message") or "")
                                    ch = _resolve_channel(guild, str(target)) if guild else None
                                    if ch:
                                        await ch.send(format_atlas_alert(msg_txt,narrated_by=args.get("narrated_by")))
                                        print("ATLAS_DISCORD_ALERT_DELIVERED",flush=True)

                                elif cap == "discord_create_note":
                                    content = str(args.get("content") or "")
                                    ch = client.get_channel(int(config.notes_channel_id)) if config.notes_channel_id else None
                                    if ch: await ch.send(f"📄 **[NOTA HERMES]** {content}")

                                elif cap == "discord_create_incident" and guild:
                                    slug = str(args.get("slug") or "alerta")
                                    desc = str(args.get("description") or "")
                                    inc_ch = await create_incident_channel(guild, slug, topic=desc)
                                    if config.alert_channel_id:
                                        ac = client.get_channel(int(config.alert_channel_id))
                                        if ac: await ac.send(f"🚨 **[INCIDENTE ABERTO POR HERMES]** Canal {getattr(inc_ch, 'mention', slug)}: {desc}")

                                elif cap == "discord_resolve_incident" and guild:
                                    slug = str(args.get("slug") or "")
                                    pm = str(args.get("post_mortem") or "")
                                    await resolve_incident_channel(guild, slug, post_mortem=pm)
                                    if config.alert_channel_id:
                                        ac = client.get_channel(int(config.alert_channel_id))
                                        if ac: await ac.send(f"✅ **[INCIDENTE RESOLVIDO POR HERMES]** `#{slug}` normalizado. Post-Mortem publicado.")

                            except Exception:
                                pass
                            last_seen += 1
                        action_cursor_file.write_text(json.dumps({"last_seen": last_seen}) + "\n", encoding="utf-8")
                except Exception:
                    pass
            await asyncio.sleep(1.0)

    @client.event
    async def on_ready():
        nonlocal pump_task, dashboard_task, actions_task, watchdog_task
        await publish_online_presence(client, discord)
        gateway_health.write("connected", reason="ready")
        print("ATLAS_DISCORD_GATEWAY_READY", flush=True)
        if pump_task is None or pump_task.done():
            pump_task=asyncio.create_task(pump_replies())
        if dashboard_task is None or dashboard_task.done():
            dashboard_task=asyncio.create_task(run_live_dashboard(client, config, state_dir))
        if actions_task is None or actions_task.done():
            actions_task=asyncio.create_task(pump_actions())
        if watchdog_task is None or watchdog_task.done():
            watchdog_task=asyncio.create_task(run_live_watchdog(client, config, state_dir))

    @client.event
    async def on_disconnect():
        gateway_health.write("disconnected", reason="gateway_disconnect")
        print("ATLAS_DISCORD_GATEWAY_DISCONNECTED", flush=True)

    @client.event
    async def on_resumed():
        await publish_online_presence(client, discord)
        gateway_health.write("connected", reason="resumed")
        print("ATLAS_DISCORD_GATEWAY_RESUMED", flush=True)

    @client.event
    async def on_message(message):
        guild=getattr(message,"guild",None)
        author=getattr(message,"author",None)
        if bool(getattr(author,"bot",False)):
            return

        content = str(getattr(message, "content", "") or "").strip()
        if content.startswith("!"):
            handled = await handle_control_command(message, client, config)
            if handled:
                return

        # Indexar toda mensagem no Grafo Relacional de Memória
        try:
            from datetime import datetime, timezone
            from .memory_model import MemoryLayer, MemoryRecord
            from .memory_store import MemoryStore

            author_name = str(getattr(author, "display_name", "") or getattr(author, "name", "") or "")
            msg_id_str = str(getattr(message, "id", ""))
            ref = getattr(message, "reference", None)
            reply_to_str = str(getattr(ref, "message_id", "") or "") or None
            ch_id_str = str(getattr(getattr(message, "channel", None), "id", "") or "")

            store = MemoryStore(state_dir / "memory.sqlite3")
            rec = MemoryRecord(
                memory_id=f"disc-{msg_id_str}",
                layer=MemoryLayer.EPISODIC,
                created_at=datetime.now(timezone.utc).isoformat(),
                entity_id="discord",
                content=f"{author_name}: {content}",
                importance=0.7 if should_respond_actively(message, client, config) else 0.4,
                confidence=0.95,
                frequency=1,
                origin="discord",
                message_id=msg_id_str,
                reply_to_id=reply_to_str,
                channel_id=ch_id_str,
                tags=("discord", ch_id_str),
            )
            store.save(rec)
            if reply_to_str:
                store.link_memories(msg_id_str, reply_to_str, "reply_of")
            store.close()
        except Exception:
            pass

        # Engajamento Ativo vs Memória Passiva do Grupo
        if should_respond_actively(message, client, config):
            async def keep_typing(ch):
                try:
                    async with ch.typing():
                        await asyncio.sleep(8.0)
                except Exception:
                    pass
            asyncio.create_task(keep_typing(getattr(message, "channel", None)))

            author_name = str(getattr(author, "display_name", "") or getattr(author, "name", "") or "")
            bridge.accept_message(
                str(getattr(message,"id","")),content,
                guild_id=str(getattr(guild,"id","") or ""),
                channel_id=str(getattr(getattr(message,"channel",None),"id","") or ""),
                user_id=str(getattr(author,"id","") or ""),
                user_name=author_name,
                is_bot=False,
            )
        else:
            record_passive_chat_memory(state_dir, message)

    try:
        await client.start(token)
    finally:
        gateway_health.write("stopped", reason="client_exit")
        for t in (pump_task, dashboard_task, actions_task, watchdog_task):
            if t is not None:
                t.cancel()
                try:
                    await t
                except asyncio.CancelledError:
                    pass


def main() -> int:
    config=load_discord_config(ROOT/"config_discord.json")
    token=resolve_discord_activation(config)
    asyncio.run(_run_discord_client(config,token))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
