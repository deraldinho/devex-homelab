import unittest

from infrastructure.pentium.atlas.adaptador_stimulus_percepcao import ConfigFontePercepcao, evidencia_de_stimulus
from infrastructure.pentium.atlas.modelo_percepcao import ResultadoEvidencia
from infrastructure.pentium.atlas.stimulus_model import Stimulus, StimulusSeverity


def stimulus(kind="status_changed", payload=None, source="core", sid="s1"):
    return Stimulus(
        stimulus_id=sid,
        source=source,
        kind=kind,
        severity=StimulusSeverity.CRITICAL,
        timestamp="2026-09-04T12:00:00+00:00",
        payload=payload or {"status": "critical"},
        novelty=1.0,
        correlation_id="c1",
    )


class AdaptadorStimulusPercepcaoTests(unittest.TestCase):
    def setUp(self):
        self.cfg = ConfigFontePercepcao("core", "core", ("tailscale_online", "ssh_reachable"), 0.8)

    def test_source_error_e_fonte_indisponivel_nao_entidade(self):
        ev = evidencia_de_stimulus(stimulus(kind="source_error"), self.cfg)
        self.assertEqual(ResultadoEvidencia.FONTE_INDISPONIVEL, ev.resultado)

    def test_critical_sem_alcance_explicito_ainda_e_observado(self):
        ev = evidencia_de_stimulus(stimulus(payload={"status": "critical"}), self.cfg)
        self.assertEqual(ResultadoEvidencia.DISPONIVEL, ev.resultado)

    def test_todos_campos_de_alcance_falsos_indicam_indisponivel(self):
        ev = evidencia_de_stimulus(
            stimulus(payload={"status": "critical", "tailscale_online": False, "ssh_reachable": False}),
            self.cfg,
        )
        self.assertEqual(ResultadoEvidencia.INDISPONIVEL, ev.resultado)

    def test_um_campo_de_alcance_verdadeiro_indica_disponivel(self):
        ev = evidencia_de_stimulus(
            stimulus(payload={"status": "degraded", "tailscale_online": False, "ssh_reachable": True}),
            self.cfg,
        )
        self.assertEqual(ResultadoEvidencia.DISPONIVEL, ev.resultado)
        self.assertEqual("s1", ev.evidencia_id)


if __name__ == "__main__":
    unittest.main()
