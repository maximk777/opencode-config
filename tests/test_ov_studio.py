import http.server
import importlib.machinery
import json
import threading
import unittest
import urllib.error
import urllib.request

S = importlib.machinery.SourceFileLoader("ov_studio", "bin/ov-studio").load_module()


class Upstream(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        body = json.dumps({"auth": self.headers.get("Authorization"), "account": self.headers.get("X-OpenViking-Account")}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(handler):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


class OvStudio(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.upstream = serve(Upstream)
        cls.proxy = serve(S.handler("user-key", f"http://127.0.0.1:{cls.upstream.server_port}", port=0))
        S_PORT = cls.proxy.server_port
        cls.proxy.RequestHandlerClass = S.handler("user-key", f"http://127.0.0.1:{cls.upstream.server_port}", port=S_PORT)
        cls.base = f"http://127.0.0.1:{S_PORT}"

    @classmethod
    def tearDownClass(cls):
        cls.proxy.shutdown()
        cls.upstream.shutdown()

    def get(self, headers=None):
        req = urllib.request.Request(self.base + "/api/v1/fs/ls", headers=headers or {})
        return json.load(urllib.request.urlopen(req, timeout=5))

    def test_injects_user_key_and_drops_browser_identity(self):
        out = self.get({"X-API-Key": "typed-in-browser", "X-OpenViking-Account": "default"})
        self.assertEqual(out, {"auth": "Bearer user-key", "account": None})

    def test_rejects_foreign_origin(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.get({"Origin": "https://evil.example"})
        self.assertEqual(e.exception.code, 403)

    def test_allows_own_origin(self):
        self.assertTrue(S.allowed_origin(None))
        self.assertTrue(S.allowed_origin("http://localhost:1934"))
        self.assertFalse(S.allowed_origin("http://127.0.0.1:1933"))


if __name__ == "__main__":
    unittest.main()
