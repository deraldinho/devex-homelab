import json
import sys
import time
from pathlib import Path
from atlas.chat_inbox import ChatInbox

def main():
    state_dir = Path.home() / "pentium-agent" / "atlas" / "runtime"
    inbox = ChatInbox(state_dir / "chat-inbox.json")
    
    custom_msg = sys.argv[1] if len(sys.argv) > 1 else "Atlas, mostre os últimos logs do gameserver"
    msg_text = f"[SUPERADMIN] - xBurg: <@1489448566081458298> {custom_msg}"
    ts = int(time.time())
    env = inbox.enqueue(
        msg_text,
        f"test_l2j_logs_{ts}",
        channel="discord",
        actor_id="1022699113562775552",
        conversation_id="1473703295611568213",
        reply_target="1473703295611568213"
    )
    print(f"-> Mensagem enfileirada no ChatInbox (ID: {env.message_id}):")
    print(f"   {env.message}")
    print("\nAguardando o atlas-cognitive daemon em execucao processar o inbox...")

    events_file = state_dir / "dashboard-events.jsonl"
    last_count = 0
    if events_file.is_file():
        last_count = len(events_file.read_text(encoding="utf-8").splitlines())

    for _ in range(25):
        time.sleep(2)
        if events_file.is_file():
            lines = events_file.read_text(encoding="utf-8").splitlines()
            if len(lines) > last_count:
                for line in lines[last_count:]:
                    try:
                        ev = json.loads(line)
                        if ev.get("type") == "chat_message" and ev.get("payload", {}).get("role") == "atlas":
                            print("\n=== RESPOSTA EMITIDA PELO ATLAS COGNITIVE DAEMON AO VIVO ===")
                            print(ev["payload"].get("message"))
                            return
                    except Exception:
                        pass
                last_count = len(lines)

    print("\nTimeout aguardando daemon processar.")

if __name__ == "__main__":
    main()
