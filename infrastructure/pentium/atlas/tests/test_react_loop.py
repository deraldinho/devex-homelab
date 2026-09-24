import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from infrastructure.pentium.atlas.action_executors import ActionExecutorRegistry
from infrastructure.pentium.atlas.action_plan import ActionStatus, ActionType, AtlasAction, PlanoAcaoAtlas
from infrastructure.pentium.atlas.cognitive_daemon import CognitiveDaemon
from infrastructure.pentium.atlas.reaction_loop_cognitivo import RespostaCognitiva


class TestReactLoop(unittest.TestCase):
    def test_react_loop_executes_tool_and_synthesizes_turn_2(self):
        # 1. Mock do loop cognitivo que responde no Turno 1 com tool call e no Turno 2 com síntese
        turn1_response = RespostaCognitiva(
            ativado=True,
            motivo="interacao_humana",
            texto="Vou sondar o L2jToren agora.",
            razao=None,
            backend="hermes",
            duracao_ms=100,
            resumo="Iniciando sonda L2j",
            intencao="l2j_get_status",
            parametros_intencao={"host": "100.101.23.111"},
            confianca=0.9,
            requer_confirmacao=False,
            intencao_autorizada=True,
        )

        turn2_response = RespostaCognitiva(
            ativado=True,
            motivo="interacao_humana",
            texto="Sondei o L2jToren: todos os 7 containers estão saudáveis e as portas UP.",
            razao=None,
            backend="hermes",
            duracao_ms=120,
            resumo="Síntese das observações da sonda",
            intencao=None,
            parametros_intencao={},
            confianca=0.98,
            requer_confirmacao=False,
            intencao_autorizada=False,
        )

        loop_mock = MagicMock()
        loop_mock.processar.side_effect = [turn1_response, turn2_response]

        # 2. Mock do capability sink
        fake_tool_result = {
            "overall_status": "HEALTHY",
            "containers_online": 7,
            "services": {"gameserver_tcp": {"status": "UP"}},
        }
        cap_sink_mock = MagicMock(return_value=fake_tool_result)

        action_executor = ActionExecutorRegistry(
            visual_getter=lambda: SimpleNamespace(expressao="SERENO"),
            visual_writer=lambda s: None,
            capability_sink=cap_sink_mock,
        )

        # 3. Mock do inbox com mensagem humana
        envelope_mock = SimpleNamespace(
            message_id="msg_react_1",
            stimulus_id="stim_react_1",
            message="Atlas, como está o L2jToren?",
            channel="discord",
            actor_id="user_123",
            conversation_id="conv_1",
            reply_target="msg_react_1",
            created_at="2026-09-20T12:00:00+00:00",
        )
        chat_inbox_mock = MagicMock()
        chat_inbox_mock.claim_next.return_value = envelope_mock

        base_snapshot = SimpleNamespace(
            source_stimulus_id="stim_react_1",
            entity_id="pentium",
            generated_at="2026-09-20T12:00:00+00:00",
            recent_changes=(),
            affective_state={"valencia": 0.5},
        )

        # 4. Mock dos demais componentes
        planner_mock = MagicMock()
        action_chat = AtlasAction(
            action_id="11111111-1111-1111-1111-111111111111",
            type=ActionType.CHAT_REPLY,
            target=None,
            parameters={},
            status=ActionStatus.AUTHORIZED,
            reason=None,
            created_at="2026-09-20T12:00:00+00:00",
            authorized_at="2026-09-20T12:00:00+00:00",
        )
        fake_plan = PlanoAcaoAtlas(
            plan_id="22222222-2222-2222-2222-222222222222",
            stimulus_id="stim_react_1",
            created_at="2026-09-20T12:00:00+00:00",
            objective="Teste",
            confidence=0.95,
            response_text=turn2_response.texto,
            actions=(action_chat,),
            requires_confirmation=False,
            policy_decision="authorized",
            trigger_kind="human_interaction",
        )
        planner_mock.plan.return_value = fake_plan

        policy_mock = MagicMock()
        policy_mock.authorize.return_value = fake_plan

        store_mock = MagicMock()
        publisher_mock = MagicMock()

        daemon = CognitiveDaemon(
            snapshot_loader=lambda: base_snapshot,
            context_provider=lambda: {"mudancas_recentes": ()},
            loop=loop_mock,
            publisher=publisher_mock,
            planner=planner_mock,
            action_policy=policy_mock,
            action_executor=action_executor,
            action_store=store_mock,
            chat_inbox=chat_inbox_mock,
        )

        # 5. Executa run_once
        res = daemon.run_once()

        # 6. Asserções
        # A capability foi executada imediatamente no ReAct loop com os argumentos fornecidos
        cap_sink_mock.assert_called_once_with("l2j_get_status", {"host": "100.101.23.111"})

        # O loop foi chamado 2 vezes (Turno 1: percepção/ação, Turno 2: síntese)
        self.assertEqual(2, loop_mock.processar.call_count)

        # A chamada do Turno 2 recebeu 'observacoes_ferramentas' no contexto
        turn2_call_kwargs = loop_mock.processar.call_args_list[1][1]
        self.assertIn("observacoes_ferramentas", turn2_call_kwargs["dados_contexto"])
        obs = turn2_call_kwargs["dados_contexto"]["observacoes_ferramentas"]
        self.assertEqual("l2j_get_status", obs[0]["capability"])
        self.assertEqual(fake_tool_result, obs[0]["result"])

        # O resultado final entregue foi o texto do Turno 2
        self.assertEqual(turn2_response.texto, res.texto)
        self.assertIsNone(res.intencao)

    def test_plain_dialogue_does_not_trigger_turn_2(self):
        # Diálogo normal sem intenção de leitura roda em turno único
        plain_response = RespostaCognitiva(
            ativado=True,
            motivo="interacao_humana",
            texto="gRPC oferece vantagens de serialização binária com Protobuf.",
            razao=None,
            backend="hermes",
            duracao_ms=90,
            resumo="Resposta arquitetural",
            intencao=None,
            parametros_intencao={},
            confianca=0.95,
            requer_confirmacao=False,
            intencao_autorizada=False,
        )

        loop_mock = MagicMock()
        loop_mock.processar.return_value = plain_response

        cap_sink_mock = MagicMock()
        action_executor = ActionExecutorRegistry(
            visual_getter=lambda: SimpleNamespace(expressao="SERENO"),
            visual_writer=lambda s: None,
            capability_sink=cap_sink_mock,
        )

        envelope_mock = SimpleNamespace(
            message_id="msg_plain_1",
            stimulus_id="stim_plain_1",
            message="Qual a vantagem de gRPC?",
            channel="discord",
            actor_id="user_123",
            conversation_id="conv_1",
            reply_target="msg_plain_1",
            created_at="2026-09-20T12:00:00+00:00",
        )
        chat_inbox_mock = MagicMock()
        chat_inbox_mock.claim_next.return_value = envelope_mock

        base_snapshot = SimpleNamespace(
            source_stimulus_id="stim_plain_1",
            entity_id="pentium",
            generated_at="2026-09-20T12:00:00+00:00",
            recent_changes=(),
            affective_state={},
        )

        daemon = CognitiveDaemon(
            snapshot_loader=lambda: base_snapshot,
            context_provider=lambda: {},
            loop=loop_mock,
            publisher=MagicMock(),
            planner=MagicMock(),
            action_policy=MagicMock(),
            action_executor=action_executor,
            action_store=MagicMock(),
            chat_inbox=chat_inbox_mock,
        )

        res = daemon.run_once()

        # Capability nunca é chamada
        cap_sink_mock.assert_not_called()
        # Loop chamado apenas 1 vez (Turno 1 único)
    def test_react_loop_executes_l2j_run_tests_and_persistence_inspection(self):
        # 1. Teste de ReAct para l2j_run_tests
        turn1_test = RespostaCognitiva(
            ativado=True,
            motivo="interacao_humana",
            texto="Executando testes de persistência...",
            razao=None,
            backend="hermes",
            duracao_ms=100,
            resumo="Disparo de testes L2jToren",
            intencao="l2j_run_tests",
            parametros_intencao={"test_target": "PlayerPersistenceTest"},
            confianca=0.95,
            requer_confirmacao=False,
            intencao_autorizada=True,
        )
        turn2_test = RespostaCognitiva(
            ativado=True,
            motivo="interacao_humana",
            texto="Os 12 testes unitários do PlayerPersistenceTest passaram com sucesso em 1.45s.",
            razao=None,
            backend="hermes",
            duracao_ms=110,
            resumo="Síntese dos testes L2jToren",
            intencao=None,
            parametros_intencao={},
            confianca=0.98,
            requer_confirmacao=False,
            intencao_autorizada=False,
        )

        loop_mock = MagicMock()
        loop_mock.processar.side_effect = [turn1_test, turn2_test]

        fake_test_result = {
            "host": "100.101.23.111",
            "target": "PlayerPersistenceTest",
            "success": True,
            "tests_run": 12,
            "failures": 0,
            "errors": 0,
            "skipped": 0,
            "summary": "Testes L2jToren (alvo 'PlayerPersistenceTest'): SUCESSO. Executados: 12, Falhas: 0, Erros: 0, Pulados: 0",
        }
        cap_sink_mock = MagicMock(return_value=fake_test_result)
        action_executor = ActionExecutorRegistry(
            visual_getter=lambda: SimpleNamespace(expressao="SERENO"),
            visual_writer=lambda s: None,
            capability_sink=cap_sink_mock,
        )

        envelope_mock = SimpleNamespace(
            message_id="msg_test_1",
            stimulus_id="stim_test_1",
            message="Atlas, rode os testes de persistencia",
            channel="discord",
            actor_id="user_123",
            conversation_id="conv_1",
            reply_target="msg_test_1",
            created_at="2026-09-24T12:00:00+00:00",
        )
        chat_inbox_mock = MagicMock()
        chat_inbox_mock.claim_next.return_value = envelope_mock

        base_snapshot = SimpleNamespace(
            source_stimulus_id="stim_test_1",
            entity_id="pentium",
            generated_at="2026-09-24T12:00:00+00:00",
            recent_changes=(),
            affective_state={"valencia": 0.6},
        )

        fake_plan = PlanoAcaoAtlas(
            plan_id="33333333-3333-3333-3333-333333333333",
            stimulus_id="stim_test_1",
            created_at="2026-09-24T12:00:00+00:00",
            objective="Teste L2j",
            confidence=0.95,
            response_text=turn2_test.texto,
            actions=(AtlasAction(
                action_id="44444444-4444-4444-4444-444444444444",
                type=ActionType.CHAT_REPLY,
                target=None,
                parameters={},
                status=ActionStatus.AUTHORIZED,
                reason=None,
                created_at="2026-09-24T12:00:00+00:00",
                authorized_at="2026-09-24T12:00:00+00:00",
            ),),
            requires_confirmation=False,
            policy_decision="authorized",
            trigger_kind="human_interaction",
        )
        planner_mock = MagicMock()
        planner_mock.plan.return_value = fake_plan
        policy_mock = MagicMock()
        policy_mock.authorize.return_value = fake_plan

        daemon = CognitiveDaemon(
            snapshot_loader=lambda: base_snapshot,
            context_provider=lambda: {"mudancas_recentes": ()},
            loop=loop_mock,
            publisher=MagicMock(),
            planner=planner_mock,
            action_policy=policy_mock,
            action_executor=action_executor,
            action_store=MagicMock(),
            chat_inbox=chat_inbox_mock,
        )

        res = daemon.run_once()

        cap_sink_mock.assert_called_once_with("l2j_run_tests", {"test_target": "PlayerPersistenceTest"})
        self.assertEqual(2, loop_mock.processar.call_count)
        self.assertEqual(turn2_test.texto, res.texto)


if __name__ == "__main__":
    unittest.main()
