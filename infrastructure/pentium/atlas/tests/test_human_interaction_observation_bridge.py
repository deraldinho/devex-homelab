import unittest

from infrastructure.pentium.atlas.human_context import CognitiveContextUnavailable
from infrastructure.pentium.atlas.human_interaction import HumanInteractionGateway
from infrastructure.pentium.atlas.tests.test_v1_human_interaction import FakeLoop, Resp


class HumanInteractionObservationBridgeTest(unittest.TestCase):
    def test_unavailable_observation_context_returns_local_response_without_loop(self):
        loop = FakeLoop(Resp())

        def unavailable():
            raise CognitiveContextUnavailable("stale")

        gateway = HumanInteractionGateway(loop, context_provider=unavailable, max_text_chars=64)
        text = gateway.handle("como esta o x99?", source="human.cli")
        self.assertEqual("Meu contexto observacional esta indisponivel no momento.", text)
        self.assertEqual([], loop.calls)


if __name__ == "__main__":
    unittest.main()
