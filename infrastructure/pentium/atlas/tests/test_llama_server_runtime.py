import unittest
from pathlib import Path

from infrastructure.pentium.atlas.llama_server_runtime import LlamaCppServerRuntime


class FakeProcess:
    def __init__(self): self.terminated = False
    def poll(self): return None
    def terminate(self): self.terminated = True
    def wait(self, timeout=None): return 0


class LlamaCppServerRuntimeTests(unittest.TestCase):
    def test_argv_usa_socket_unix_sem_tcp_e_sem_slot_persistido(self):
        calls = []; proc = FakeProcess()
        runtime = LlamaCppServerRuntime(Path('/opt/llama-server'), Path('/models/q.gguf'), Path('/run/user/1000/atlas-llm.sock'), context_size=4096, cache_reuse=64, starter=lambda argv, **kw: calls.append((argv, kw)) or proc)
        runtime.start()
        argv, kwargs = calls[0]
        host_arg = argv[argv.index('--host') + 1]
        self.assertTrue(host_arg.replace('\\', '/').endswith('/atlas-llm.sock'))
        self.assertIn('--cache-prompt', argv)
        self.assertIn('--cache-reuse', argv)
        self.assertNotIn('--slot-save-path', argv)
        self.assertFalse(kwargs['shell'])

    def test_stop_encerra_processo_owned(self):
        proc = FakeProcess()
        runtime = LlamaCppServerRuntime(Path('/opt/llama-server'), Path('/models/q.gguf'), Path('/tmp/a.sock'), context_size=2048, cache_reuse=32, starter=lambda argv, **kw: proc)
        runtime.start(); runtime.stop()
        self.assertTrue(proc.terminated)


class LlamaCppServerStaleSocketTests(unittest.TestCase):
    def test_start_remove_socket_stale_before_spawn(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp:
            socket_path = Path(tmp) / 'atlas-llm.sock'
            socket_path.write_text('stale', encoding='utf-8')
            seen = []
            proc = FakeProcess()
            runtime = LlamaCppServerRuntime(Path('/opt/llama-server'), Path('/models/q.gguf'), socket_path, context_size=4096, cache_reuse=64, starter=lambda argv, **kw: seen.append(socket_path.exists()) or proc)
            runtime.start()
            self.assertEqual([False], seen)

    def test_stop_remove_socket_owned(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp:
            socket_path = Path(tmp) / 'atlas-llm.sock'
            proc = FakeProcess()
            runtime = LlamaCppServerRuntime(Path('/opt/llama-server'), Path('/models/q.gguf'), socket_path, context_size=2048, cache_reuse=32, starter=lambda argv, **kw: proc)
            runtime.start(); socket_path.write_text('owned', encoding='utf-8'); runtime.stop()
            self.assertFalse(socket_path.exists())
