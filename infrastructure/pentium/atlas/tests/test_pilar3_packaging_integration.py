"""Atlas 4.0 — Pilar 3: Packaging and End-to-End Integration Tests.

Valida empacotamento no instalador e o fluxo integrado completo do Pilar 3:
Autonomia Técnica e Gestão Proativa de Tarefas:
HypothesisEngine + TaskTracker + SelfWorkStore + TaskCapabilityExecutor + ContextoCognitivo.
"""
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.autonomy.hypothesis_engine import (
    Hypothesis,
    HypothesisEngine,
    HypothesisStatus,
)
from infrastructure.pentium.atlas.autonomy.task_tracker import (
    AtlasTask,
    TaskPriority,
    TaskSource,
    TaskStatus,
    TaskTracker,
)
from infrastructure.pentium.atlas.configuracao_cognitiva import PoliticaContextoCognitivo
from infrastructure.pentium.atlas.contexto_cognitivo import ContextoCognitivoBuilder
from infrastructure.pentium.atlas.emocao_derivada import EmocaoDerivada
from infrastructure.pentium.atlas.modelo_afetivo import EstadoAfetivo
from infrastructure.pentium.atlas.modelo_contexto_cognitivo import MotivoAtivacaoCognitiva
from infrastructure.pentium.atlas.modelo_foco import AssuntoFoco, FocoAtencao
from infrastructure.pentium.atlas.modelo_percepcao import EstadoObservacao, EstadoPercepcao
from infrastructure.pentium.atlas.self_work import SelfWorkRuntime, SelfWorkState
from infrastructure.pentium.atlas.state_model import GlobalAssessment, TechnicalState
from infrastructure.pentium.atlas.task_capability_executor import TaskCapabilityExecutor
from infrastructure.pentium.atlas.task_store import SelfWorkStore


class Pilar3PackagingTests(unittest.TestCase):
    def test_installer_empacota_modulos_pilar3(self):
        text = Path("infrastructure/pentium/atlas/install-user.sh").read_text(encoding="utf-8")
        for filename in (
            "autonomy/__init__.py",
            "autonomy/hypothesis_engine.py",
            "autonomy/task_tracker.py",
            "task_store.py",
            "task_capability_executor.py",
        ):
            self.assertIn(filename, text)
        self.assertIn("ATLAS_AUTONOMY_INSTALL_PASS", text)


class Pilar3IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.hypo_path = self.tmp_path / "hypotheses.json"
        self.task_tracker_path = self.tmp_path / "tasks.json"
        self.current_json = self.tmp_path / "self-work-current.json"
        self.history_jsonl = self.tmp_path / "self-work-history.jsonl"

        self.hypo_engine = HypothesisEngine(self.hypo_path)
        self.task_tracker = TaskTracker(self.task_tracker_path)
        self.self_work_store = SelfWorkStore(self.current_json, self.history_jsonl)
        self.self_work_runtime = SelfWorkRuntime(
            ttl_s=600,
            store=self.self_work_store,
            id_factory=lambda: "task-pilar3-auto",
        )
        self.task_executor = TaskCapabilityExecutor(self.self_work_runtime)
        self.builder = ContextoCognitivoBuilder(
            PoliticaContextoCognitivo(
                max_string_chars=256,
                max_mudancas_recentes=8,
                max_dependencias_afetadas=8,
                max_nuances=3,
                max_payload_bytes=8192,
            )
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_pilar3_full_pipeline_roundtrip(self):
        # 1. Formulação de Hipótese Técnica baseada em observação/tendência
        hypo = self.hypo_engine.propose(
            hypothesis_id="hypo-leak-pentium",
            title="Vazamento gradual de memória em processo de background no Pentium",
            description="RAM subindo 2.5%/hora continuamente sem liberação pelo GC",
            source="trend:pentium:ram_percent",
            related_entities=["node:pentium"],
        )
        self.assertEqual(hypo.status, HypothesisStatus.PROPOSED)
        self.assertEqual(hypo.hypothesis_id, "hypo-leak-pentium")

        # 2. Investigação e Adição de Evidências
        self.hypo_engine.add_evidence(
            "hypo-leak-pentium",
            evidence="Swap aumentando proporcionalmente ao RSS",
            supports=True,
        )
        self.hypo_engine.add_evidence(
            "hypo-leak-pentium",
            evidence="Processo atlas-observation alocando buffers sem descarte",
            supports=True,
        )

        hypo_updated = self.hypo_engine.get("hypo-leak-pentium")
        self.assertIsNotNone(hypo_updated)
        self.assertEqual(hypo_updated.status, HypothesisStatus.INVESTIGATING)
        self.assertGreater(hypo_updated.confidence, 0.5)

        # 3. Resolução da Hipótese como Confirmada
        resolved = self.hypo_engine.resolve(
            "hypo-leak-pentium",
            status=HypothesisStatus.CONFIRMED,
            note="Confirmado buffer leak no coletor de métricas",
        )
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.status, HypothesisStatus.CONFIRMED)

        # 4. Geração Proativa de Tarefa via TaskTracker baseada na hipótese confirmada
        task = self.task_tracker.suggest_from_hypothesis(
            hypothesis_id="hypo-leak-pentium",
            title="Aplicar expurgo cíclico de buffers no coletor de observação do Pentium",
        )
        self.assertEqual(task.source, TaskSource.HYPOTHESIS)
        self.assertEqual(task.source_ref, "hypo-leak-pentium")
        self.assertEqual(task.status, TaskStatus.OPEN)

        # 5. Acionamento e Execução do Ciclo de Autonomia via TaskCapabilityExecutor
        # Consulta inicial
        status_idle = self.task_executor("task_status", {})
        self.assertFalse(status_idle["has_active_task"])

        # Criação/ativação da tarefa via capability
        created_res = self.task_executor(
            "task_create",
            {
                "objective": task.title,
                "area": "infrastructure",
            },
        )
        self.assertEqual(created_res["status"], "CREATED")
        self.assertEqual(created_res["item_id"], "task-pilar3-auto")

        # Verifica status ativo
        status_active = self.task_executor("task_status", {})
        self.assertTrue(status_active["has_active_task"])
        self.assertEqual(status_active["status"], "WORKING")
        self.assertEqual(status_active["item_id"], "task-pilar3-auto")

        # 6. Validação de Persistência e Recuperação após Restart
        new_runtime = SelfWorkRuntime(ttl_s=600, store=self.self_work_store)
        self.assertIsNone(new_runtime.current)
        restored = new_runtime.restore_from_store(now="2026-09-22T20:01:00+00:00")
        self.assertIsNotNone(restored)
        self.assertEqual(restored.item_id, "task-pilar3-auto")
        self.assertEqual(restored.state, SelfWorkState.WORKING)

        # Conclusão da tarefa
        complete_res = self.task_executor(
            "task_complete",
            {"reason": "Buffer cíclico implementado e estabilizado"},
        )
        self.assertEqual(complete_res["status"], "COMPLETED")
        self.assertEqual(complete_res["item_id"], "task-pilar3-auto")
        self.assertIsNone(self.self_work_runtime.current)
        status_after = self.task_executor("task_status", {})
        self.assertFalse(status_after["has_active_task"])

        # 7. Construção do ContextoCognitivo com as hipóteses ativas integradas
        assessment = GlobalAssessment(TechnicalState.HEALTHY, TechnicalState.HEALTHY, 0, ())
        percepcao = EstadoPercepcao("node:pentium", EstadoObservacao.OBSERVADO, 0.95, None, (), (), False, "2026-09-22T20:00:00+00:00")
        estado_afetivo = EstadoAfetivo(0.3, 0.4, 0.1, 0.8, 0.6, 0.7, "2026-09-22T20:00:00+00:00", "node:pentium")
        foco = FocoAtencao(AssuntoFoco("node:pentium", "node:pentium", 1, 0.8, 1, 1, 1, 1), (), "2026-09-22T20:00:00+00:00", 1)

        hipoteses_payload = (
            {
                "hypothesis_id": hypo_updated.hypothesis_id,
                "title": hypo_updated.title,
                "status": hypo_updated.status.value,
                "confidence": round(hypo_updated.confidence, 2),
                "source": hypo_updated.source,
                "related_entities": hypo_updated.related_entities,
            },
        )

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
            dependencias_afetadas=("node:pentium",),
            agora="2026-09-22T20:00:00+00:00",
            hipoteses_ativas=hipoteses_payload,
        )

        # Validações do ContextoCognitivo com hipóteses ativas do Pilar 3
        self.assertEqual(ctx.entidade_principal, "node:pentium")
        self.assertEqual(ctx.emocao_principal, "atento")
        self.assertEqual(len(ctx.hipoteses_ativas), 1)
        self.assertEqual(ctx.hipoteses_ativas[0]["hypothesis_id"], "hypo-leak-pentium")
        self.assertEqual(ctx.hipoteses_ativas[0]["status"], "confirmed")
        self.assertLessEqual(ctx.payload_bytes(), 8192)


if __name__ == "__main__":
    unittest.main()
