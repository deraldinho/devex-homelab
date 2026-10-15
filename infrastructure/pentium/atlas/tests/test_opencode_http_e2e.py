"""End-to-end loopback HTTP transport with real sockets and a fake provider."""
import base64
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from infrastructure.pentium.atlas.opencode_http_transport import OpenCodeHTTPTransport

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def respond(self,payload):
        raw=json.dumps({"data":payload}).encode()
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
    def do_POST(self):
        expected="Basic "+base64.b64encode(b"opencode:test-pass").decode()
        if self.headers.get("Authorization")!=expected:
            self.send_error(401);return
        size=int(self.headers.get("Content-Length","0"))
        payload=json.loads(self.rfile.read(size))
        if self.path=="/api/session":
            self.server.created+=1
            self.respond({"id":"test-session","location":payload["location"]})
        elif self.path=="/api/session/test-session/prompt":
            self.server.prompts+=1
            self.respond({})
        else:self.send_error(404)
    def do_GET(self):
        if self.path=="/api/session/test-session":
            self.server.polls+=1
            self.respond({"outcome":"running" if self.server.polls==1 else "succeeded"})
        elif self.path=="/api/session/test-session/message":
            self.respond([{"type":"assistant","content":[{"type":"text","text":"safe completed reply"}]}])
        else:self.send_error(404)

class LoopbackIntegrationTests(unittest.TestCase):
    def test_resume_over_real_http_without_duplicate_prompt(self):
        with tempfile.TemporaryDirectory() as folder:
            server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
            server.created=server.prompts=server.polls=0
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            try:
                args={"base_url":"http://127.0.0.1:"+str(server.server_port),
                      "password":"test-pass","directory":folder,
                      "journal_path":Path(folder)/"journal.json"}
                job={"model":"free","prompt":"code","context":"{}","max_tokens":10}
                first=OpenCodeHTTPTransport(**args)
                with self.assertRaises(TimeoutError):first(**job)
                second=OpenCodeHTTPTransport(**args)
                self.assertEqual(second(**job)["text"],"safe completed reply")
                self.assertEqual(second(**job)["text"],"safe completed reply")
                self.assertEqual((server.created,server.prompts),(1,1))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)
if __name__=="__main__":unittest.main()
