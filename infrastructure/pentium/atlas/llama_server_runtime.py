from __future__ import annotations

import subprocess
from pathlib import Path


class LlamaCppServerRuntime:
    def __init__(self, binary_path: Path, model_path: Path, socket_path: Path, *, context_size: int, cache_reuse: int, starter=subprocess.Popen):
        if context_size <= 0 or cache_reuse < 0:
            raise ValueError("bounds invalidos")
        self._binary = Path(binary_path)
        self._model = Path(model_path)
        self._socket = Path(socket_path)
        self._context_size = int(context_size)
        self._cache_reuse = int(cache_reuse)
        self._starter = starter
        self._proc = None

    def start(self):
        if self._proc is not None and self._proc.poll() is None:
            return self._proc
        self._socket.unlink(missing_ok=True)
        argv = [str(self._binary), "-m", str(self._model), "-c", str(self._context_size), "--host", str(self._socket), "--cache-prompt", "--cache-reuse", str(self._cache_reuse)]
        self._proc = self._starter(argv, shell=False, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return self._proc

    def stop(self):
        proc, self._proc = self._proc, None
        if proc is not None and proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=5)
        self._socket.unlink(missing_ok=True)
