from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[4]
ATLAS = ROOT / "infrastructure" / "pentium" / "atlas"


class S3FastDispatchPackagingTests(unittest.TestCase):
    def test_arquitetura_e_prd_oficializam_fast_dispatch_s3(self):
        architecture = (ROOT / "docs" / "architecture" / "atlas-local-intelligence-design.md").read_text(encoding="utf-8")
        prd = (ROOT / "docs" / "prd" / "PRD-0006-atlas-local-intelligence.md").read_text(encoding="utf-8")
        self.assertIn("Fast Dispatch S3", architecture)
        self.assertIn("SLOW_LLM apenas agenda", architecture)
        self.assertIn("RF10 - Fast Dispatch deterministico", prd)
        self.assertIn("S3 - Fast Dispatch", prd)

    def test_dispatch_e_queue_nao_importam_io_ou_caminho_cognitivo_concreto(self):
        source = (ATLAS / "fast_dispatch.py").read_text(encoding="utf-8")
        source += (ATLAS / "slow_llm_defer_queue.py").read_text(encoding="utf-8")
        proibidos = (
            "llm_gateway", "reaction_loop_cognitivo", "subprocess", "socket",
            "requests", "urllib", "paramiko",
        )
        for proibido in proibidos:
            self.assertNotIn(proibido, source)
    def test_installer_e_ci_empacotam_s3_e_marker(self):
        installer = (ATLAS / "install-user.sh").read_text(encoding="utf-8")
        ci = (ROOT / ".github" / "workflows" / "foundation-ci.yml").read_text(encoding="utf-8")
        for nome in (
            "modelo_fast_dispatch.py",
            "fast_dispatch.py",
            "slow_llm_defer_queue.py",
        ):
            self.assertIn(nome, installer)
            self.assertIn(nome, ci)
        self.assertIn("ATLAS_FAST_DISPATCH_S3_INSTALL_PASS", installer)
        self.assertIn("DEVEX_HOMELAB_ATLAS_FAST_DISPATCH_S3_PASS", ci)


if __name__ == "__main__":
    unittest.main()
