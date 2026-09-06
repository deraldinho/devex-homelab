import inspect
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.sampler_linux_cognitivo import LinuxCognitiveSampler


class C5PhysicalRunnerContractTests(unittest.TestCase):
    def test_sampler_exige_pid_llm_e_fonte_termica_explicitos(self):
        sig = inspect.signature(LinuxCognitiveSampler)
        self.assertIs(inspect.Parameter.empty, sig.parameters['thermal_path'].default)
        self.assertIs(inspect.Parameter.empty, sig.parameters['llm_status_path'].default)

    def test_runner_nao_executa_shell_e_exige_identidade_do_head(self):
        from infrastructure.pentium.atlas.c5_physical_runner import construir_parser
        parser = construir_parser()
        args = parser.parse_args([
            '--llm-pid', '321', '--socket', '/run/user/1000/atlas.sock',
            '--expected-sha', 'a' * 40,
        ])
        self.assertEqual(321, args.llm_pid)
        self.assertEqual(Path('/run/user/1000/atlas.sock'), args.socket)
        self.assertEqual('a' * 40, args.expected_sha)


if __name__ == '__main__':
    unittest.main()
