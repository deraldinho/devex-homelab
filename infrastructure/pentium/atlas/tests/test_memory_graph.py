import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.memory_model import MemoryLayer, MemoryRecord
from infrastructure.pentium.atlas.memory_retriever import MemoryRetriever
from infrastructure.pentium.atlas.memory_store import MemoryStore


class MemoryGraphTests(unittest.TestCase):
    def test_link_and_traverse_conversation_thread(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.db")

            # 1. Criar thread encadeada de 3 mensagens: msg-1 -> msg-2 -> msg-3
            m1 = MemoryRecord(
                "mem-1", MemoryLayer.EPISODIC, "2026-09-19T01:00:00+00:00",
                "discord", "Operador: Como está o disco do Core?",
                0.7, 0.9, 1, "discord", message_id="msg-1"
            )
            m2 = MemoryRecord(
                "mem-2", MemoryLayer.EPISODIC, "2026-09-19T01:00:05+00:00",
                "discord", "Atlas: O disco do Core está em 63%, estável.",
                0.7, 0.9, 1, "discord", message_id="msg-2", reply_to_id="msg-1"
            )
            m3 = MemoryRecord(
                "mem-3", MemoryLayer.EPISODIC, "2026-09-19T01:01:00+00:00",
                "discord", "Operador: Ótimo, continue monitorando.",
                0.6, 0.9, 1, "discord", message_id="msg-3", reply_to_id="msg-2"
            )

            store.save(m1)
            store.save(m2)
            store.save(m3)

            # Criar link relacional explícito
            store.link_memories("msg-2", "msg-1", "reply_of")
            store.link_memories("msg-3", "msg-2", "reply_of")

            # Testar get_by_message_id
            rec = store.get_by_message_id("msg-2")
            self.assertIsNotNone(rec)
            self.assertEqual("mem-2", rec.memory_id)
            self.assertEqual("msg-1", rec.reply_to_id)

            # Testar travessia de thread a partir de msg-3
            thread = store.get_connected_thread("msg-3")
            self.assertEqual(3, len(thread))
            self.assertEqual(["msg-1", "msg-2", "msg-3"], [m.message_id for m in thread])

            store.close()

    def test_associated_memories_graph_lookup(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.db")

            m_incident = MemoryRecord(
                "mem-inc-1", MemoryLayer.SEMANTIC, "2026-09-18T10:00:00+00:00",
                "core", "Incidente de disco no Core saneado liberando 70GB",
                0.9, 0.95, 3, "incident_engine", tags=("incidente", "disco", "core")
            )
            m_chat = MemoryRecord(
                "mem-chat-1", MemoryLayer.EPISODIC, "2026-09-19T02:00:00+00:00",
                "discord", "Operador: Qual foi a causa do incidente de ontem?",
                0.8, 0.9, 1, "discord", message_id="msg-100"
            )

            store.save(m_incident)
            store.save(m_chat)

            store.link_memories("msg-100", "mem-inc-1", "references_incident", weight=2.0)

            # Buscar memórias associadas a msg-100
            associated = store.get_associated_memories("msg-100")
            self.assertEqual(1, len(associated))
            self.assertEqual("mem-inc-1", associated[0].memory_id)

            store.close()

    def test_memory_retriever_prioritizes_thread_and_associated_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.db")

            # Mensagens de outra conversa aleatória (mais recentes)
            for i in range(10):
                store.save(MemoryRecord(
                    f"noise-{i}", MemoryLayer.EPISODIC, f"2026-09-19T03:{i:02d}:00+00:00",
                    "discord", f"Conversa aleatória sobre almoço {i}",
                    0.3, 0.5, 1, "discord", message_id=f"noise-msg-{i}"
                ))

            # Conversa específica sobre backup ocorrida mais cedo
            store.save(MemoryRecord(
                "backup-1", MemoryLayer.EPISODIC, "2026-09-19T01:00:00+00:00",
                "backup", "Backup restic rodou com sucesso gerando snapshot #42",
                0.8, 0.9, 1, "backup", message_id="msg-backup-parent"
            ))
            store.save(MemoryRecord(
                "backup-2", MemoryLayer.EPISODIC, "2026-09-19T01:01:00+00:00",
                "backup", "Confirmado upload para GitHub Release privada",
                0.8, 0.9, 1, "backup", message_id="msg-backup-child", reply_to_id="msg-backup-parent"
            ))

            retriever = MemoryRetriever(store, max_items=5)

            # Ao responder à mensagem 'msg-backup-child', o retriever deve trazer a thread pai
            # em vez de ser sufocado pelas 10 mensagens de ruído recentes!
            results = retriever.retrieve(reply_to_id="msg-backup-child", query_terms=("backup",))
            msg_ids = [r.get("message_id") for r in results]

            self.assertIn("msg-backup-parent", msg_ids)
            self.assertIn("msg-backup-child", msg_ids)
            # A thread conectada vem em primeiro lugar!
            self.assertEqual("msg-backup-parent", results[0]["message_id"])

            store.close()


if __name__ == "__main__":
    unittest.main()
