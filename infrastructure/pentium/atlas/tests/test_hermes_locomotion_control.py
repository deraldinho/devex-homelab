import unittest
from types import SimpleNamespace
from dataclasses import replace

from infrastructure.pentium.atlas.action_plan import ActionStatus, ActionType, AtlasAction, PlanoAcaoAtlas
from infrastructure.pentium.atlas.action_planner import ActionPlanner
from infrastructure.pentium.atlas.action_executors import ActionExecutorRegistry
from infrastructure.pentium.atlas.modelo_visual_atlas import EstadoVisualAtlas, ModoVisual, ExpressaoVisual


def make_response(**overrides):
    values = dict(
        texto="Verificando.", resumo="resumo", confianca=0.85,
        motivo="interacao_humana", intencao=None, parametros_intencao=None,
        requer_confirmacao=False, solicitar_fala=False,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def make_visual_state():
    return EstadoVisualAtlas(
        modo=ModoVisual.OCIOSO,
        expressao=ExpressaoVisual.SERENO,
        intensidade_expressao=0.5,
        foco_visual="centro",
        direcao_olhar="frente",
        gesto_atual="NENHUM",
        velocidade_movimento=0.5,
        intensidade_movimento=0.5,
        falando=False,
        ouvindo=False,
        pensando=False,
        duvida_identidade=False,
        transicao_ms=300,
        alvo_locomocao="auto",
        acao_pet="PATROL",
    )


class HermesLocomotionControlTests(unittest.TestCase):
    def test_action_creation_and_parameter_validation(self):
        nav = AtlasAction.create(ActionType.NAVIGATE_TO, target="mind", parameters={"target": "mind", "mode": "hop"})
        self.assertEqual(ActionType.NAVIGATE_TO, nav.type)
        self.assertEqual("mind", nav.parameters["target"])

        pet = AtlasAction.create(ActionType.SET_PET_ACTION, parameters={"action": "SIT", "duration_ms": 5000})
        self.assertEqual(ActionType.SET_PET_ACTION, pet.type)
        self.assertEqual("SIT", pet.parameters["action"])

        # Parâmetro inválido deve levantar ValueError
        with self.assertRaises(ValueError):
            AtlasAction.create(ActionType.NAVIGATE_TO, parameters={"comando_invalido": 123})

    def test_planner_generates_explicit_locomotion_intent(self):
        resp = make_response(intencao="mover_para", parametros_intencao={"target": "services", "mode": "hop"})
        plan = ActionPlanner().plan("s1", "pentium", resp)
        nav_actions = [a for a in plan.actions if a.type is ActionType.NAVIGATE_TO]
        self.assertTrue(len(nav_actions) > 0)
        self.assertEqual("services", nav_actions[0].parameters["target"])

    def test_planner_generates_explicit_pet_action_intent(self):
        resp = make_response(intencao="acao_pet", parametros_intencao={"action": "POKE", "duration_ms": 1200})
        plan = ActionPlanner().plan("s1", "pentium", resp)
        pet_actions = [a for a in plan.actions if a.type is ActionType.SET_PET_ACTION]
        self.assertTrue(len(pet_actions) > 0)
        self.assertEqual("POKE", pet_actions[0].parameters["action"])

    def test_planner_contextual_chat_navigation(self):
        resp = make_response(texto="Olá Deraldinho, estou aqui!", motivo="interacao_humana")
        plan = ActionPlanner().plan("s1", "deraldinho", resp, trigger_kind="chat")
        nav_actions = [a for a in plan.actions if a.type is ActionType.NAVIGATE_TO]
        self.assertTrue(len(nav_actions) > 0)
        self.assertEqual("chat", nav_actions[0].parameters["target"])

    def test_planner_contextual_friendly_poke_and_sit(self):
        resp_sit = make_response(texto="Pode descansar e sentar um pouco agora.", motivo="interacao_humana")
        plan_sit = ActionPlanner().plan("s1", "deraldinho", resp_sit, trigger_kind="chat")
        pet_sit = next(a for a in plan_sit.actions if a.type is ActionType.SET_PET_ACTION)
        self.assertEqual("SIT", pet_sit.parameters["action"])

        resp_poke = make_response(texto="Muito obrigado pelo carinho, fico feliz!", motivo="interacao_humana")
        plan_poke = ActionPlanner().plan("s2", "deraldinho", resp_poke, trigger_kind="chat")
        pet_poke = next(a for a in plan_poke.actions if a.type is ActionType.SET_PET_ACTION)
        self.assertEqual("POKE", pet_poke.parameters["action"])

    def test_action_executor_updates_visual_state_locomotion(self):
        current_state = make_visual_state()
        written_states = []

        def writer(st):
            written_states.append(st)

        executor = ActionExecutorRegistry(visual_getter=lambda: current_state, visual_writer=writer)

        # 1. Executar NAVIGATE_TO
        nav_action = AtlasAction.create(ActionType.NAVIGATE_TO, target="mind", parameters={"target": "mind", "mode": "hop"})
        plan1 = PlanoAcaoAtlas.create(
            stimulus_id="s1",
            objective="mover para mind",
            confidence=0.9,
            response_text=None,
            actions=[replace(nav_action, status=ActionStatus.AUTHORIZED)],
        )
        executor.execute(plan1)
        self.assertEqual(1, len(written_states))
        self.assertEqual("mind", written_states[-1].alvo_locomocao)
        self.assertEqual("mind", written_states[-1].foco_visual)

        # 2. Executar SET_PET_ACTION
        pet_action = AtlasAction.create(ActionType.SET_PET_ACTION, parameters={"action": "SIT", "duration_ms": 6000})
        plan2 = PlanoAcaoAtlas.create(
            stimulus_id="s2",
            objective="sentar na janela",
            confidence=0.9,
            response_text=None,
            actions=[replace(pet_action, status=ActionStatus.AUTHORIZED)],
        )
        executor.execute(plan2)
        self.assertEqual(2, len(written_states))
        self.assertEqual("SIT", written_states[-1].acao_pet)


if __name__ == "__main__":
    unittest.main()
