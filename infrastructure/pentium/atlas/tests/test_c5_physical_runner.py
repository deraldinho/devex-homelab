import inspect
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.sampler_linux_cognitivo import LinuxCognitiveSampler


class C5PhysicalRunnerContractTests(unittest.TestCase):
    def test_sampler_exige_fonte_termica_sem_pid_llm_local(self):
        sig = inspect.signature(LinuxCognitiveSampler)
        self.assertIs(inspect.Parameter.empty, sig.parameters['thermal_path'].default)
        self.assertNotIn('llm_status_path', sig.parameters)

    def test_runner_exige_sha_e_config_hermes_sem_socket_ou_pid(self):
        from infrastructure.pentium.atlas.c5_physical_runner import construir_parser
        parser = construir_parser()
        args = parser.parse_args([
            '--expected-sha', 'a' * 40,
            '--hermes-config', '/tmp/config_hermes.json',
        ])
        self.assertEqual('a' * 40, args.expected_sha)
        self.assertEqual(Path('/tmp/config_hermes.json'), args.hermes_config)
        self.assertFalse(hasattr(args, 'llm_pid'))
        self.assertFalse(hasattr(args, 'socket'))


if __name__ == '__main__':
    unittest.main()
