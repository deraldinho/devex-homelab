import unittest

from infrastructure.pentium.atlas.capability_registry import CapabilityRegistry, CapabilitySpec
from infrastructure.pentium.atlas.policy_capabilities import PolicyCapabilities


class PolicyCapabilitiesTests(unittest.TestCase):
    def setUp(self):
        self.registry = CapabilityRegistry([
            CapabilitySpec("get_host_status", "READ", ("host",), tipos_parametros=(("host", "str"),)),
            CapabilitySpec("restart_service", "CONTROL", ("host", "service"), tipos_parametros=(("host", "str"), ("service", "str"))),
            CapabilitySpec("reboot_host", "DESTRUCTIVE", ("host",), tipos_parametros=(("host", "str"),)),
        ])
        self.policy = PolicyCapabilities(
            self.registry,
            read_auto_allow=("get_host_status",),
            control_allow=("restart_service",),
        )

    def test_read_allowlisted_pode_ser_autorizada_automaticamente(self):
        decisao = self.policy.avaliar("get_host_status", {"host": "core"})
        self.assertTrue(decisao.autorizada)
        self.assertFalse(decisao.requer_confirmacao)
    def test_control_exige_autorizacao_explicita_da_policy(self):
        sem = PolicyCapabilities(self.registry, read_auto_allow=("get_host_status",), control_allow=())
        self.assertFalse(sem.avaliar("restart_service", {"host": "core", "service": "docker"}).autorizada)
        com = self.policy.avaliar("restart_service", {"host": "core", "service": "docker"})
        self.assertTrue(com.autorizada)
        self.assertFalse(com.requer_confirmacao)

    def test_destructive_sempre_exige_confirmacao_humana_independente(self):
        decisao = self.policy.avaliar("reboot_host", {"host": "core"})
        self.assertFalse(decisao.autorizada)
        self.assertTrue(decisao.requer_confirmacao)
        confirmado = self.policy.avaliar("reboot_host", {"host": "core"}, confirmacao_humana=True)
        self.assertTrue(confirmado.autorizada)

    def test_intencao_parametros_invalidos_e_capability_desconhecida_falham_fechado(self):
        self.assertFalse(self.policy.avaliar("get_host_status", {"host": 123}).autorizada)
        self.assertFalse(self.policy.avaliar("get_host_status", {"host": "core", "extra": "x"}).autorizada)
        self.assertFalse(self.policy.avaliar("shell", {"command": "id"}).autorizada)


if __name__ == "__main__":
    unittest.main()
