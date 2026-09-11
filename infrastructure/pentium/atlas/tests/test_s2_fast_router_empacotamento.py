from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[4]
ATLAS = ROOT / "infrastructure" / "pentium" / "atlas"


class S2FastRouterPackagingTests(unittest.TestCase):
    def test_arquitetura_e_prd_oficializam_fast_slow_sem_llm_no_critical_path(self):
        architecture = (ROOT / "docs" / "architecture" / "atlas-local-intelligence-design.md").read_text(encoding="utf-8")
        prd = (ROOT / "docs" / "prd" / "PRD-0006-atlas-local-intelligence.md").read_text(encoding="utf-8")
        self.assertIn("Fast Router S2", architecture)
        self.assertIn("SLOW_LLM", architecture)
        self.assertIn("RF9 - Fast Router deterministico", prd)
        self.assertIn("S2 - Fast Router", prd)

    def test_router_nao_importa_caminhos_lentos_ou_io(self):
        source = (ATLAS / "fast_router.py").read_text(encoding="utf-8")
        proibidos = (
            "llm_gateway",
            "cognitive_cache",
            "subprocess",
            "socket",
            "requests",
            "urllib",
            "paramiko",
        )
        for proibido in proibidos:
            self.assertNotIn(proibido, source)

    def test_installer_e_ci_empacotam_s2_e_config(self):
        installer = (ATLAS / "install-user.sh").read_text(encoding="utf-8")
        ci = (ROOT / ".github" / "workflows" / "foundation-ci.yml").read_text(encoding="utf-8")
        for nome in (
            "modelo_fast_router.py",
            "configuracao_fast_router.py",
            "fast_router.py",
            "config_fast_router.json",
        ):
            self.assertIn(nome, installer)
            self.assertIn(nome, ci)
        self.assertIn("ATLAS_FAST_ROUTER_S2_INSTALL_PASS", installer)
        self.assertIn("DEVEX_HOMELAB_ATLAS_FAST_ROUTER_S2_PASS", ci)


if __name__ == "__main__":
    unittest.main()
