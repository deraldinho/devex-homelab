import socket
import unittest
from unittest.mock import patch

from infrastructure.pentium.atlas.unix_http import post_json_unix


class FakeSocket:
    def __init__(self, chunks): self.chunks = list(chunks)
    def settimeout(self, value): pass
    def connect(self, path): pass
    def sendall(self, data): pass
    def recv(self, size): return self.chunks.pop(0) if self.chunks else b''
    def close(self): pass


class UnixHttpTests(unittest.TestCase):
    def test_rejeita_resposta_acima_do_bound(self):
        raw = b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n' + b'x' * 40
        fake = FakeSocket([raw])
        with patch.object(socket, 'AF_UNIX', 1, create=True), patch('infrastructure.pentium.atlas.unix_http.socket.socket', return_value=fake):
            with self.assertRaises(ValueError):
                post_json_unix('/tmp/a.sock', '/completion', {'x':1}, 1, 16)
