import unittest

from infrastructure.pentium.atlas.memory_model import MemoryLayer, MemoryRecord


class MemoryModelTests(unittest.TestCase):
    def test_camadas_l0_l3_sao_explicitas(self):
        self.assertEqual(
            {"working", "episodic", "semantic", "relational"},
            {item.value for item in MemoryLayer},
        )

    def test_registro_valida_bounds_e_normaliza(self):
        registro = MemoryRecord(
            memory_id="m1", layer=MemoryLayer.EPISODIC,
            created_at="2026-09-05T17:00:00-03:00", entity_id="core",
            content=" Core reiniciou ", importance=0.8, confidence=0.9,
            frequency=2, origin="observation", criticality=0.7,
        )
        self.assertEqual("Core reiniciou", registro.content)
        self.assertEqual("2026-09-05T20:00:00+00:00", registro.created_at)
        with self.assertRaises(ValueError):
            MemoryRecord("x", MemoryLayer.WORKING, registro.created_at, None, "x", 1.2, 0.5, 1, "human")


if __name__ == "__main__":
    unittest.main()
