import unittest

from infrastructure.pentium.atlas.cognitive_router import CognitiveRoute, CognitiveRouter
from infrastructure.pentium.atlas.token_budget_governor import TokenBudgetGovernor


class CognitiveRouterTests(unittest.TestCase):
    def setUp(self):
        self.governor = TokenBudgetGovernor(window_budget=1000)
        self.router = CognitiveRouter(self.governor)

    def test_workspace_status_e_list_sao_deterministicos(self):
        self.assertEqual(CognitiveRoute.DETERMINISTIC, self.router.route(kind="self_work", operation="workspace_status", fingerprint="a"))
        self.assertEqual(CognitiveRoute.DETERMINISTIC, self.router.route(kind="self_work", operation="workspace_list", fingerprint="b"))

    def test_estado_inalterado_sem_deadline_nao_infere(self):
        self.assertEqual(CognitiveRoute.LLM, self.router.route(kind="observation", fingerprint="same"))
        self.assertEqual(CognitiveRoute.NO_INFERENCE_REQUIRED, self.router.route(kind="observation", fingerprint="same"))

    def test_cache_e_retrieval_precedem_llm(self):
        self.assertEqual(CognitiveRoute.CACHE, self.router.route(kind="self_work", fingerprint="c", cache_hit=True))
        self.assertEqual(CognitiveRoute.RETRIEVAL, self.router.route(kind="self_work", fingerprint="d", retrieval_sufficient=True))

    def test_interacao_humana_nao_e_suprimida_por_fingerprint(self):
        self.assertEqual(CognitiveRoute.LLM, self.router.route(kind="human", fingerprint="h"))
        self.assertEqual(CognitiveRoute.LLM, self.router.route(kind="human", fingerprint="h"))

    def test_self_work_bloqueado_sob_pressao(self):
        self.governor.record(900)
        self.assertEqual(CognitiveRoute.NO_INFERENCE_REQUIRED, self.router.route(kind="self_work", fingerprint="w"))

    def test_deadline_forca_avaliacao_mesmo_sem_mudanca(self):
        self.assertEqual(CognitiveRoute.LLM, self.router.route(kind="observation", fingerprint="x"))
        self.assertEqual(CognitiveRoute.LLM, self.router.route(kind="observation", fingerprint="x", deadline_due=True))
