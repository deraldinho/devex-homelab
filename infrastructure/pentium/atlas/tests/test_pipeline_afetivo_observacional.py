import unittest

from infrastructure.pentium.atlas.adaptador_impacto_afetivo import ImpactoAfetivoObservacional
from infrastructure.pentium.atlas.emocao_derivada import ContextoEmocional
from infrastructure.pentium.atlas.modelo_afetivo import EstadoAfetivo, ImpulsoAfetivo
from infrastructure.pentium.atlas.modelo_contexto_afetivo import TipoExperienciaOperacional
from infrastructure.pentium.atlas.modelo_foco import AssuntoFoco
from infrastructure.pentium.atlas.modelo_incidente import EstadoRecuperacaoIncidente, IncidenteTecnico
from infrastructure.pentium.atlas.modelo_percepcao import EstadoObservacao, EstadoPercepcao
from infrastructure.pentium.atlas.pipeline_afetivo_observacional import PipelineAfetivoObservacional
from infrastructure.pentium.atlas.pipeline_percepcao_correlacao import ResultadoPipelinePercepcaoCorrelacao
from infrastructure.pentium.atlas.stimulus_model import Stimulus, StimulusSeverity

NOW = "2026-09-08T03:00:00+00:00"


def stim(sid):
    return Stimulus(sid, "core.agent", "status_changed", StimulusSeverity.WARNING, NOW, {}, 1.0, "c", None, sid)


def perception():
    return EstadoPercepcao("core", EstadoObservacao.INACESSIVEL, 0.8, NOW, (), ("core.agent",), False, NOW)


def incident(state):
    return IncidenteTecnico("inc-1", "core", "down", "critical", NOW, "core", 1.0, ("core",), 1, estado_recuperacao=state, recuperado_em=NOW if state is EstadoRecuperacaoIncidente.RECUPERADO else None)


def impact(recovered=False):
    return ImpactoAfetivoObservacional(
        ImpulsoAfetivo("x", delta_estresse=-0.2 if recovered else 0.2),
        AssuntoFoco("inc-1", "core", 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, True, recovered),
        ContextoEmocional(recuperacao_relevante=recovered, criticidade_relevante=not recovered),
        "inc-1", "core",
    )


class FakeA3:
    def __init__(self, results):
        self.results = iter(results)
        self.calls = 0
    def processar(self, stimulus):
        self.calls += 1
        return next(self.results)


class FakeA2:
    def __init__(self, known=True):
        self.known = known
        self.experiences = []
    def vinculo_efetivo(self, entidade_id):
        if not self.known:
            raise KeyError(entidade_id)
        return None
    def fator_reincidencia(self, entidade_id, agora, *, janela_s, limite_repeticoes):
        if not self.known:
            raise KeyError(entidade_id)
        return 0.0
    def registrar_experiencia(self, experiencia):
        if not self.known:
            raise KeyError(experiencia.entidade_id)
        self.experiences.append(experiencia)
        return True


class FakeAdapter:
    def __init__(self, impacts):
        self.impacts = iter(impacts)
    def derivar(self, stimulus, result, vinculo, reincidencia):
        return next(self.impacts)


class FakeMotor:
    def __init__(self):
        self.calls = 0
    def aplicar_impulso(self, impulso, ocorrido_em=None):
        self.calls += 1
        return EstadoAfetivo(0, 0.5, 0.4, 0.5, 0.5, 0.5, ocorrido_em)


class FakeA4:
    def __init__(self):
        self.calls = 0
    def processar(self, estado, assuntos, contexto, agora):
        self.calls += 1
        return (estado, assuntos, contexto, agora)


class FakeVisual:
    def __init__(self):
        self.results = []
    def atualizar_resultado(self, result, *, reacao_critica=False):
        self.results.append((result, reacao_critica))
        return result


def make_pipeline(results, impacts, *, known=True):
    a3 = FakeA3(results)
    a2 = FakeA2(known=known)
    motor = FakeMotor()
    a4 = FakeA4()
    visual = FakeVisual()
    pipeline = PipelineAfetivoObservacional(
        pipeline_percepcao=a3,
        contexto_afetivo=a2,
        adaptador=FakeAdapter(impacts),
        motor_afetivo=motor,
        contexto_foco_emocao=a4,
        affective_runtime=visual,
        capacidade_stimulus_ids=8,
        capacidade_incidentes=8,
        capacidade_assuntos=4,
        capacidade_erros=4,
        janela_reincidencia_s=3600.0,
        limite_repeticoes=3,
    )
    return pipeline, a3, a2, motor, a4, visual


class PipelineAfetivoObservacionalTests(unittest.TestCase):
    def test_duplicate_stimulus_does_not_apply_second_impulse(self):
        result = ResultadoPipelinePercepcaoCorrelacao(True, perception(), (incident(EstadoRecuperacaoIncidente.ABERTO),))
        pipeline, a3, a2, motor, a4, visual = make_pipeline([result], [impact()])
        first = pipeline.processar(stim("s-1"))
        second = pipeline.processar(stim("s-1"))
        self.assertTrue(first.aceito)
        self.assertFalse(second.aceito)
        self.assertEqual(1, a3.calls)
        self.assertEqual(1, motor.calls)
        self.assertEqual(1, a4.calls)
        self.assertEqual(1, len(visual.results))

    def test_incident_open_and_recovery_register_each_transition_once(self):
        opened = ResultadoPipelinePercepcaoCorrelacao(True, perception(), (incident(EstadoRecuperacaoIncidente.ABERTO),))
        recovered = ResultadoPipelinePercepcaoCorrelacao(True, perception(), (incident(EstadoRecuperacaoIncidente.RECUPERADO),))
        pipeline, _, a2, motor, _, _ = make_pipeline([opened, recovered], [impact(), impact(True)])
        pipeline.processar(stim("s-1"))
        pipeline.processar(stim("s-2"))
        self.assertEqual(
            [TipoExperienciaOperacional.INCIDENTE, TipoExperienciaOperacional.RECUPERACAO],
            [item.tipo for item in a2.experiences],
        )
        self.assertEqual(2, motor.calls)

    def test_unknown_a2_entity_is_diagnostic_not_pipeline_failure(self):
        result = ResultadoPipelinePercepcaoCorrelacao(True, perception(), (incident(EstadoRecuperacaoIncidente.ABERTO),))
        pipeline, _, _, motor, _, visual = make_pipeline([result], [impact()], known=False)
        processed = pipeline.processar(stim("s-1"))
        self.assertTrue(processed.aceito)
        self.assertEqual(1, motor.calls)
        self.assertEqual(1, len(visual.results))
        self.assertTrue(any(item.startswith("contexto_afetivo:") for item in pipeline.errors()))

    def test_errors_collection_is_bounded(self):
        results = [ResultadoPipelinePercepcaoCorrelacao(True, perception(), ()) for _ in range(6)]
        impacts = [impact() for _ in range(6)]
        pipeline, *_ = make_pipeline(results, impacts, known=False)
        for index in range(6):
            pipeline.processar(stim(f"s-{index}"))
        self.assertLessEqual(len(pipeline.errors()), 4)


if __name__ == "__main__":
    unittest.main()
