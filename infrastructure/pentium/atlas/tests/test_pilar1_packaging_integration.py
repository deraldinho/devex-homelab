"""Atlas 4.0 — Pilar 1: Packaging and End-to-End Integration Tests.

Valida empacotamento no instalador e o fluxo integrado completo do Pilar 1:
MemoryGraph + MemoryStore v3 + MemoryProjectAdapter + PreferenceTracker +
MemoryRetriever + ContextoCognitivo.
"""
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.configuracao_cognitiva import PoliticaContextoCognitivo
from infrastructure.pentium.atlas.contexto_cognitivo import ContextoCognitivoBuilder
from infrastructure.pentium.atlas.emocao_derivada import EmocaoDerivada
from infrastructure.pentium.atlas.memory_graph import (
    EntityType,
    MemoryGraph,
    RelationType,
)
from infrastructure.pentium.atlas.memory_model import MemoryLayer, MemoryRecord
from infrastructure.pentium.atlas.memory_preference_tracker import (
    PreferenceSignal,
    PreferenceTracker,
)
from infrastructure.pentium.atlas.memory_project_adapter import MemoryProjectAdapter
from infrastructure.pentium.atlas.memory_retriever import MemoryRetriever
from infrastructure.pentium.atlas.memory_store import MemoryStore
from infrastructure.pentium.atlas.modelo_afetivo import EstadoAfetivo
from infrastructure.pentium.atlas.modelo_contexto_cognitivo import MotivoAtivacaoCognitiva
from infrastructure.pentium.atlas.modelo_foco import AssuntoFoco, FocoAtencao
from infrastructure.pentium.atlas.modelo_percepcao import EstadoObservacao, EstadoPercepcao
from infrastructure.pentium.atlas.state_model import GlobalAssessment, TechnicalState


class Pilar1PackagingTests(unittest.TestCase):
    def test_installer_empacota_modulos_pilar1(self):
        text = Path("infrastructure/pentium/atlas/install-user.sh").read_text(encoding="utf-8")
        for filename in (
            "memory_graph.py",
            "memory_project_adapter.py",
            "memory_preference_tracker.py",
        ):
            self.assertIn(filename, text)
        self.assertIn("ATLAS_MEMORY_GRAPH_M3_INSTALL_PASS", text)


class Pilar1IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "memory.db"
        self.pref_path = Path(self.tmp.name) / "pref.json"

        self.store = MemoryStore(self.db_path)
        self.graph = MemoryGraph(self.db_path)
        self.adapter = MemoryProjectAdapter(self.graph)
        self.tracker = PreferenceTracker(self.pref_path)
        self.retriever = MemoryRetriever(
            self.store,
            graph=self.graph,
            preference_tracker=self.tracker,
            max_items=5,
            max_bytes=4096,
        )
        self.builder = ContextoCognitivoBuilder(
            PoliticaContextoCognitivo(max_string_chars=256, max_mudancas_recentes=8, max_dependencias_afetadas=8, max_nuances=3, max_payload_bytes=8192)
        )

    def tearDown(self):
        self.graph.close()
        self.store.close()
        self.tmp.cleanup()

    def test_pilar1_full_pipeline_roundtrip(self):
        # 1. Popula topologia baseline no grafo relacional
        count = self.adapter.ensure_homelab_baseline()
        self.assertGreaterEqual(len(count), 5)

        # Verifica nós e relações
        l2j = self.graph.get_entity("proj:l2jtoren")
        self.assertIsNotNone(l2j)
        self.assertEqual(l2j.name, "L2jToren")

        # 2. Registra preferência do operador para o tópico L2jToren
        self.tracker.record(PreferenceSignal("topic", "l2jtoren", 1.0, "2026-09-22T14:00:00+00:00"))
        self.tracker.record(PreferenceSignal("schedule", "active_hour:14", 1.0, "2026-09-22T14:00:00+00:00"))
        self.tracker.record(PreferenceSignal("style", "direct", 1.0, "2026-09-22T14:00:00+00:00"))

        # 3. Salva memórias no MemoryStore v3 (uma sobre L2jToren, uma genérica)
        self.store.save(MemoryRecord(
            "mem-l2j", MemoryLayer.SEMANTIC, "2026-09-22T14:05:00+00:00",
            "proj:l2jtoren", "L2jToren gameserver opera na porta 7777 no host x99",
            importance=0.9, confidence=0.95, frequency=2, origin="human",
        ))
        self.store.save(MemoryRecord(
            "mem-general", MemoryLayer.EPISODIC, "2026-09-22T14:00:00+00:00",
            "node:pentium", "Pentium load average normal 0.15",
            importance=0.4, confidence=0.8, frequency=1, origin="observation",
        ))

        # 4. Retrieval semântico contextual enriquecido com grafo e preferências
        retrieved_memories = self.retriever.retrieve(
            entity_id="proj:l2jtoren",
            query_terms=("l2jtoren", "gameserver"),
        )
        self.assertTrue(len(retrieved_memories) >= 1)
        self.assertEqual(retrieved_memories[0]["memory_id"], "mem-l2j")

        # Contexto relacional de entidades do grafo
        graph_context = self.retriever.retrieve_graph_context("proj:l2jtoren", limit=5)
        self.assertGreaterEqual(len(graph_context), 1)

        # 5. Constrói ContextoCognitivo expandido
        assessment = GlobalAssessment(TechnicalState.HEALTHY, TechnicalState.HEALTHY, 0, ())
        percepcao = EstadoPercepcao("proj:l2jtoren", EstadoObservacao.OBSERVADO, 0.95, None, (), (), False, "2026-09-22T14:10:00+00:00")
        estado_afetivo = EstadoAfetivo(0.3, 0.4, 0.1, 0.8, 0.6, 0.7, "2026-09-22T14:10:00+00:00", "proj:l2jtoren")
        foco = FocoAtencao(AssuntoFoco("proj:l2jtoren", "proj:l2jtoren", 1, 0.8, 1, 1, 1, 1), (), "2026-09-22T14:10:00+00:00", 1)

        ctx = self.builder.construir(
            motivo=MotivoAtivacaoCognitiva.INTERACAO_HUMANA,
            assessment=assessment,
            percepcao=percepcao,
            incidente=None,
            estado_afetivo=estado_afetivo,
            emocao=EmocaoDerivada("atento", ("confiante",)),
            foco=foco,
            expectativa=None,
            mudancas_recentes=(),
            dependencias_afetadas=("node:x99",),
            agora="2026-09-22T14:10:00+00:00",
            memorias_relevantes=retrieved_memories,
            grafo_conhecimento=graph_context,
            preferencias_operador={
                "active_hours": self.tracker.profile.schedule_hours,
                "top_topics": self.tracker.profile.topics,
                "preferred_styles": self.tracker.profile.styles,
            },
        )

        # Validações do ContextoCognitivo integrado
        self.assertEqual(ctx.entidade_principal, "proj:l2jtoren")
        self.assertEqual(ctx.emocao_principal, "atento")
        self.assertEqual(len(ctx.memorias_relevantes), len(retrieved_memories))
        self.assertGreaterEqual(len(ctx.grafo_conhecimento), 1)
        self.assertIn("l2jtoren", ctx.preferencias_operador["top_topics"])
        self.assertLessEqual(ctx.payload_bytes(), 8192)


if __name__ == "__main__":
    unittest.main()
