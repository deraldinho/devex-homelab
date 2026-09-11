import socket
import unittest
from unittest.mock import patch

from infrastructure.pentium.atlas.unix_http import get_json_unix, post_json_unix


class FakeSocket:
    def __init__(self, chunks): self.chunks = list(chunks)
    def settimeout(self, value): pass
    def connect(self, path): pass
    def sendall(self, data): self.sent = data
    def recv(self, size): return self.chunks.pop(0) if self.chunks else b''
    def close(self): pass


class UnixHttpTests(unittest.TestCase):
    def test_get_json_unix_monta_get_bounded_e_parseia_json(self):
        raw = b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 15\r\n\r\n{"status":"ok"}'
        fake = FakeSocket([raw])
        with patch.object(socket, 'AF_UNIX', 1, create=True), patch('infrastructure.pentium.atlas.unix_http.socket.socket', return_value=fake):
            status, data = get_json_unix('/tmp/a.sock', '/health', 1, 128)
        self.assertEqual(200, status)
        self.assertEqual({'status': 'ok'}, data)
        self.assertTrue(fake.sent.startswith(b'GET /health HTTP/1.1\r\n'))

    def test_rejeita_resposta_acima_do_bound(self):
        raw = b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n' + b'x' * 40
        fake = FakeSocket([raw])
        with patch.object(socket, 'AF_UNIX', 1, create=True), patch('infrastructure.pentium.atlas.unix_http.socket.socket', return_value=fake):
            with self.assertRaises(ValueError):
                post_json_unix('/tmp/a.sock', '/completion', {'x':1}, 1, 16)


class KeepAliveSocket(FakeSocket):
    def recv(self, size):
        if self.chunks:
            return self.chunks.pop(0)
        raise TimeoutError('keep-alive socket stayed open')


class UnixHttpKeepAliveTests(unittest.TestCase):
    def test_content_length_terminates_without_waiting_for_eof(self):
        raw = b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 15\r\nConnection: keep-alive\r\n\r\n{"status":"ok"}'
        fake = KeepAliveSocket([raw])
        with patch.object(socket, 'AF_UNIX', 1, create=True), patch('infrastructure.pentium.atlas.unix_http.socket.socket', return_value=fake):
            status, data = get_json_unix('/tmp/a.sock', '/health', 1, 128)
        self.assertEqual(200, status)
        self.assertEqual({'status': 'ok'}, data)
