import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


class K2PackagingTests(unittest.TestCase):
    def test_installer_empacota_k2_sem_start_automatico(self):
        text = (ROOT / 'infrastructure/pentium/atlas/install-user.sh').read_text(encoding='utf-8')
        for name in ('unix_http.py','config_hermes.json','hermes_adapter.py','ATLAS_COGNITIVE_CACHE_K2_INSTALL_PASS'):
            self.assertIn(name, text)
        for legacy in ('llama_server_runtime.py','llama_cpp_resident_backend.py','config_llama_server.json'):
            self.assertNotIn(legacy, text)
        self.assertNotIn('systemctl --user enable --now atlas-llm', text)

    def test_ci_compila_valida_e_marca_k2(self):
        text = (ROOT / '.github/workflows/foundation-ci.yml').read_text(encoding='utf-8')
        for name in ('hermes_adapter.py','config_hermes.py','unix_http.py','config_hermes.json','DEVEX_HOMELAB_ATLAS_COGNITIVE_CACHE_K2_PASS'):
            self.assertIn(name, text)
        for legacy in ('llama_server_runtime.py','llama_cpp_resident_backend.py','config_llama_server.json'):
            self.assertNotIn(legacy, text)
