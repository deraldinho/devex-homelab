import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


class S1SemanticBoundaryPackagingTests(unittest.TestCase):
    def test_arquitetura_e_prd_proibem_dicionario_nos_servicos(self):
        architecture = (ROOT / "docs/architecture/atlas-local-intelligence-design.md").read_text(encoding="utf-8")
        prd = (ROOT / "docs/prd/PRD-0006-atlas-local-intelligence.md").read_text(encoding="utf-8")
        self.assertIn("Nenhum serviço externo depende do vocabulário", architecture)
        self.assertIn("FronteiraSemantica", architecture)
        self.assertIn("vocabulário semântico interno do Atlas", prd)
        self.assertIn("S1 — Semantic Event + Adapter Boundary", prd)

    def test_installer_e_ci_empacotam_todos_modulos_s1(self):
        installer = (ROOT / "infrastructure/pentium/atlas/install-user.sh").read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/foundation-ci.yml").read_text(encoding="utf-8")
        for module in ("modelo_evento_semantico.py", "registro_semantico.py", "adaptadores_semanticos.py"):
            self.assertIn(module, installer)
            self.assertIn(module, workflow)
        self.assertIn("DEVEX_HOMELAB_ATLAS_SEMANTIC_S1_PASS", workflow)

    def test_contratos_externos_nao_importam_registry_atlas(self):
        external = [
            ROOT / "infrastructure/network/health.py",
            ROOT / "infrastructure/pentium/heartbeat/heartbeat.py",
            ROOT / "infrastructure/pentium/agent/agent.py",
        ]
        for path in external:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("registro_semantico", text)
            self.assertNotIn("EventoSemantico", text)


if __name__ == "__main__":
    unittest.main()
