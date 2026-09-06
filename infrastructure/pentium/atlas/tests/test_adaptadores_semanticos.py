import unittest

from infrastructure.pentium.atlas.adaptadores_semanticos import (
    ErroFronteiraSemantica,
    criar_fronteira_semantica_padrao,
)
from infrastructure.pentium.atlas.modelo_evento_semantico import (
    EntidadeSemantica,
    EstadoSemantico,
    TipoEventoSemantico,
)
from infrastructure.pentium.atlas.stimulus_model import Stimulus, StimulusSeverity


class AdaptadoresSemanticosTests(unittest.TestCase):
    def _stimulus(self, source, kind="status_changed", payload=None, severity=StimulusSeverity.WARNING):
        return Stimulus(
            stimulus_id="stim-1",
            source=source,
            kind=kind,
            severity=severity,
            timestamp="2026-09-06T00:00:00+00:00",
            payload=payload or {"status": "degraded"},
            novelty=0.75,
            correlation_id="corr-1",
            current_fingerprint="f" * 64,
        )

    def test_core_traduz_status_sem_expor_vocabulario_ao_servico(self):
        fronteira = criar_fronteira_semantica_padrao()
        stimulus = self._stimulus("core", payload={"status": "degraded", "ssh_reachable": False, "tailscale_online": True})
        (evento,) = fronteira.traduzir(stimulus)
        self.assertEqual(EntidadeSemantica.CORE, evento.entity)
        self.assertEqual(TipoEventoSemantico.STATE_CHANGED, evento.event)
        self.assertEqual(EstadoSemantico.DEGRADED, evento.state)
        self.assertEqual({"ssh_reachable": False, "tailscale_online": True}, dict(evento.attributes))

    def test_pentium_achata_somente_metricas_bounded(self):
        fronteira = criar_fronteira_semantica_padrao()
        stimulus = self._stimulus(
            "pentium.self",
            payload={
                "status": "healthy",
                "metrics": {"memory_available_mb": 1500, "disk_free_percent": 72.5},
                "checks": {"a": True, "b": False},
            },
            severity=StimulusSeverity.INFO,
        )
        (evento,) = fronteira.traduzir(stimulus)
        self.assertEqual(EntidadeSemantica.PENTIUM, evento.entity)
        self.assertEqual(EstadoSemantico.HEALTHY, evento.state)
        self.assertEqual(1500, evento.attributes["memory_available_mb"])
        self.assertEqual(72.5, evento.attributes["disk_free_percent"])
        self.assertEqual(1, evento.attributes["failed_checks"])

    def test_source_error_e_recovery_sao_explicitos(self):
        fronteira = criar_fronteira_semantica_padrao()
        erro = self._stimulus("x99", kind="source_error", payload={"status": "error", "error_type": "TimeoutError"})
        recovered = self._stimulus("x99", kind="recovered", payload={"status": "healthy"}, severity=StimulusSeverity.NOTICE)
        (e1,) = fronteira.traduzir(erro)
        (e2,) = fronteira.traduzir(recovered)
        self.assertEqual((TipoEventoSemantico.SOURCE_ERROR, EstadoSemantico.ERROR), (e1.event, e1.state))
        self.assertEqual((TipoEventoSemantico.RECOVERED, EstadoSemantico.HEALTHY), (e2.event, e2.state))

    def test_wifi_faz_fanout_sem_carregar_lista_original(self):
        fronteira = criar_fronteira_semantica_padrao()
        stimulus = self._stimulus(
            "wifi.presence",
            payload={
                "status": "healthy",
                "zone": "WIFI_OBSERVED",
                "devices": [{"mac": "aa:bb:cc:dd:ee:01"}],
                "events": [
                    {"kind": "appeared", "mac": "aa:bb:cc:dd:ee:01", "changed_fields": []},
                    {"kind": "changed", "mac": "aa:bb:cc:dd:ee:02", "changed_fields": ["ipv4", "hostname"]},
                ],
            },
            severity=StimulusSeverity.INFO,
        )
        eventos = fronteira.traduzir(stimulus)
        self.assertEqual(2, len(eventos))
        self.assertEqual(TipoEventoSemantico.PRESENCE_APPEARED, eventos[0].event)
        self.assertEqual(EstadoSemantico.PRESENT, eventos[0].state)
        self.assertEqual({"mac": "aa:bb:cc:dd:ee:01"}, dict(eventos[0].attributes))
        self.assertEqual(TipoEventoSemantico.PRESENCE_CHANGED, eventos[1].event)
        self.assertEqual(2, eventos[1].attributes["changed_count"])

    def test_wifi_baseline_e_um_evento_agregado(self):
        fronteira = criar_fronteira_semantica_padrao()
        stimulus = self._stimulus("wifi.presence", kind="baseline_observed", payload={"status": "healthy", "devices": [{"mac": "a"}, {"mac": "b"}], "events": []}, severity=StimulusSeverity.INFO)
        (evento,) = fronteira.traduzir(stimulus)
        self.assertEqual(TipoEventoSemantico.OBSERVED, evento.event)
        self.assertEqual(2, evento.attributes["device_count"])

    def test_fonte_desconhecida_falha_fechado(self):
        fronteira = criar_fronteira_semantica_padrao()
        with self.assertRaises(ErroFronteiraSemantica):
            fronteira.traduzir(self._stimulus("servico.externo"))

    def test_wifi_rejeita_fanout_acima_de_32(self):
        fronteira = criar_fronteira_semantica_padrao()
        events = [
            {"kind": "appeared", "mac": f"aa:bb:cc:dd:ee:{i:02x}", "changed_fields": []}
            for i in range(33)
        ]
        stimulus = self._stimulus(
            "wifi.presence",
            payload={"status": "healthy", "devices": [], "events": events},
            severity=StimulusSeverity.INFO,
        )
        with self.assertRaises(ErroFronteiraSemantica):
            fronteira.traduzir(stimulus)


if __name__ == "__main__":
    unittest.main()
