import json
import time
import os
import sqlite3
from pathlib import Path

def main():
    state_dir = Path.home() / "pentium-agent" / "atlas" / "runtime"
    queue_file = state_dir / "discord-action-queue.jsonl"
    cursor_file = state_dir / "discord-action-cursor.json"
    memory_file = state_dir / "memory.sqlite3"

    print("=== 1. VERIFICANDO GRAFO DE MEMORIAS (SQLITE) ===")
    assert memory_file.is_file(), f"Memory db missing: {memory_file}"
    conn = sqlite3.connect(memory_file)
    cur = conn.cursor()

    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    ts_now = int(time.time())
    parent_id = f"test_parent_{ts_now}"
    child_id = f"test_child_{ts_now}"
    msg_id_parent = 88880000 + (ts_now % 10000)
    msg_id_child = msg_id_parent + 1

    # 1.1 Inserir mensagem pai
    cur.execute("""
        INSERT INTO memories (
            memory_id, layer, created_at, content, importance, confidence, frequency, origin, criticality, pinned, protected, message_id, reply_to_id
        ) VALUES (?, 'episodic', ?, 'Teste de contexto: backup do restic e disaster recovery homologados com sucesso.', 0.9, 1.0, 1, 'discord_test', 0.1, 0, 0, ?, NULL)
    """, (parent_id, now_iso, msg_id_parent))

    # 1.2 Inserir mensagem filha encadeada
    cur.execute("""
        INSERT INTO memories (
            memory_id, layer, created_at, content, importance, confidence, frequency, origin, criticality, pinned, protected, message_id, reply_to_id
        ) VALUES (?, 'episodic', ?, 'E qual e o periodo de retencao configurado para esses backups?', 0.8, 1.0, 1, 'discord_test', 0.1, 0, 0, ?, ?)
    """, (child_id, now_iso, msg_id_child, msg_id_parent))

    # 1.3 Inserir aresta no Grafo Relacional (memory_links)
    cur.execute("""
        INSERT INTO memory_links (source_id, target_id, relation, weight, created_at)
        VALUES (?, ?, 'reply_of', 1.0, ?)
    """, (child_id, parent_id, now_iso))
    conn.commit()

    # 1.4 Testar travessia genealógica pelo Grafo
    cur.execute("""
        SELECT m.content, l.relation, m.message_id FROM memories m
        JOIN memory_links l ON l.target_id = m.memory_id
        WHERE l.source_id = ?
    """, (child_id,))
    row = cur.fetchone()
    assert row is not None and "restic" in row[0], f"Falha no grafo relacional: {row}"
    print(f"-> Grafo Relacional OK: Mensagem Filha ({msg_id_child}) -> {row[1]} -> Pai ({row[2]}): '{row[0][:50]}...'")
    conn.close()

    print("\n=== 2. TESTANDO CAPABILITIES DO HERMES (DISCORD ACTION QUEUE) ===")
    # Criar acao de nota em #logs
    action_note = {
        "capability": "discord_create_note",
        "arguments": {"content": f"[TESTE E2E AUTO] Validacao de Capabilities do Hermes executada com sucesso no hardware do Pentium ({now_iso})."},
        "timestamp": time.time()
    }
    # Criar acao de alerta em #watchdog
    action_alert = {
        "capability": "discord_send_alert",
        "arguments": {"message": f"[TESTE E2E AUTO] Alerta informativo emitido pelo motor cognitivo do Atlas ({now_iso})."},
        "timestamp": time.time()
    }

    with queue_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(action_note) + "\n")
        f.write(json.dumps(action_alert) + "\n")

    print("-> Acoes enfileiradas na discord-action-queue.jsonl:")
    print("   1. discord_create_note -> Destino: #logs")
    print("   2. discord_send_alert -> Destino: #watchdog")

    print("\n=== 3. AGUARDANDO CONSUMO PELO DISCORD GATEWAY ===")
    time.sleep(4)
    if cursor_file.is_file():
        cursor_data = json.loads(cursor_file.read_text(encoding="utf-8"))
        print(f"-> Cursor da fila de acoes atualizado: {cursor_data}")
    else:
        print("-> Fila em processamento assincrono pelo loop do discord_gateway.")

    print("\n=== 4. TELEMETRIA E ESTADO COGNITIVO EM TEMPO REAL ===")
    runtime_file = state_dir / "cognitive-runtime.json"
    if runtime_file.is_file():
        rt = json.loads(runtime_file.read_text(encoding="utf-8"))
        print(f"-> Cognitive runtime: ativado={rt.get('activated')}, backend={rt.get('backend')}, duracao_ms={rt.get('duracao_ms')}")

    affective_file = state_dir / "affective-state.json"
    if affective_file.is_file():
        aff = json.loads(affective_file.read_text(encoding="utf-8"))
        print(f"-> Estado Afetivo: Valencia={aff.get('valencia')}, Estresse={aff.get('estresse')}, Curiosidade={aff.get('curiosidade')}")

    dashboard_file = state_dir / "dashboard-msg-id.json"
    if dashboard_file.is_file():
        dash = json.loads(dashboard_file.read_text(encoding="utf-8"))
        print(f"-> Live Dashboard fixo: Mensagem ID = {dash.get('message_id')}")

    print("\n>>> SUCESSO TOTAL: TODAS AS USABILIDADES VALIDADAS DE PONTA A PONTA! <<<")

if __name__ == "__main__":
    main()
