import unittest

from infrastructure.pentium.atlas.capability_registry import atlas_capability_registry


class M2ControlCapabilitiesTests(unittest.TestCase):
    def test_registry_declares_m2_levels_and_parameters(self):
        registry = atlas_capability_registry()
        expected = {
            "start_service": ("CONTROL", ("host", "service")),
            "stop_service": ("CONTROL", ("host", "service")),
            "restart_service": ("CONTROL", ("host", "service")),
            "restart_container": ("CONTROL", ("host", "container")),
            "reboot_host": ("DESTRUCTIVE", ("host",)),
        }
        for name, (level, params) in expected.items():
            spec = registry.obter(name)
            self.assertEqual(spec.nivel, level)
            self.assertEqual(spec.parametros, params)
        self.assertNotIn("shell", registry.listar())


if __name__ == "__main__":
    unittest.main()
