import unittest
from types import SimpleNamespace

from infrastructure.pentium.atlas.cognitive_daemon import CognitiveDaemon
from infrastructure.pentium.atlas.modelo_contexto_cognitivo import (
    DecisaoAtivacaoCognitiva, MotivoAtivacaoCognitiva,
)
from infrastructure.pentium.atlas.modelo_llm_gateway import ResultadoInferencia
from infrastructure.pentium.atlas.reaction_loop_cognitivo import ReactionLoopCognitivo


class InferenceLifecycleTests(unittest.TestCase):
    def run_cycle(self, *, blocked=False, cached=False, failure=False):
        states, phases, gateway_states = [], [], []
        result = ResultadoInferencia(True, "ok", None, 1, "fake")
        policy = SimpleNamespace(
            avaliar=lambda **kw: DecisaoAtivacaoCognitiva(
                not blocked, None if blocked else MotivoAtivacaoCognitiva.NOVIDADE_RELEVANTE,
                "cooldown" if blocked else None,
            ),
            registrar_ativacao=lambda *args: None,
        )

        def inferir(*args):
            gateway_states.append(list(states))
            if failure:
                raise TimeoutError("backend unavailable")
            return result

        cache = SimpleNamespace(allowed=lambda _: True, get=lambda *args: result)
        loop = ReactionLoopCognitivo(
            policy, SimpleNamespace(construir=lambda **kw: object()),
            SimpleNamespace(inferir=inferir), cognitive_cache=cache if cached else None,
        )
        snapshot = SimpleNamespace(
            source_stimulus_id="s1", generated_at="2026-09-11T12:00:00+00:00",
            recent_changes=(), affective_state={},
        )
        publisher = SimpleNamespace(
            publish_phase=lambda *args, **kw: phases.append(kw["state"]),
            publish=lambda *args: None,
        )
        daemon = CognitiveDaemon(
            lambda: snapshot, lambda: {}, loop, publisher,
            visual_state_sink=lambda state: states.append(state.pensando),
        )
        if failure:
            with self.assertRaises(TimeoutError):
                daemon.run_once()
        else:
            daemon.run_once()
        return states, phases, gateway_states

    def test_policy_block_does_not_publish_thinking(self):
        states, phases, calls = self.run_cycle(blocked=True)
        self.assertEqual([], states)
        self.assertEqual(["ANALISANDO"], phases)
        self.assertEqual([], calls)

    def test_cache_hit_does_not_publish_thinking(self):
        states, phases, calls = self.run_cycle(cached=True)
        self.assertEqual([], states)
        self.assertNotIn("INFERINDO", phases)
        self.assertEqual([], calls)

    def test_thinking_covers_only_gateway_call(self):
        states, phases, calls = self.run_cycle()
        self.assertEqual([True, False], states)
        self.assertEqual([[True]], calls)
        self.assertEqual(["ANALISANDO", "INFERINDO"], phases)

    def test_gateway_exception_clears_thinking_and_reports_failure(self):
        states, phases, calls = self.run_cycle(failure=True)
        self.assertEqual([True, False], states)
        self.assertEqual([[True]], calls)
        self.assertEqual("DEGRADADA", phases[-1])
