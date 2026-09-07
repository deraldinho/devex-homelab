import unittest

from infrastructure.pentium.atlas.capability_registry import CapabilityRegistry, CapabilitySpec


class CapabilityRegistryTests(unittest.TestCase):
    def test_registro_expoe_apenas_capabilities_tipadas_allowlisted(self):
        registry = CapabilityRegistry([
            CapabilitySpec("get_host_status", "READ", ("host",)),
            CapabilitySpec("restart_service", "CONTROL", ("host", "service")),
        ])
        self.assertEqual(("get_host_status", "restart_service"), registry.listar())
        spec = registry.obter("get_host_status")
        self.assertEqual("READ", spec.nivel)
        self.assertEqual(("host",), spec.parametros)

    def test_capability_desconhecida_e_rejeitada(self):
        registry = CapabilityRegistry([])
        with self.assertRaises(KeyError):
            registry.obter("shell")

    def test_nivel_invalido_e_rejeitado(self):
        with self.assertRaises(ValueError):
            CapabilitySpec("x", "ROOT", ())
