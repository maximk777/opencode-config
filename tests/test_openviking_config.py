import importlib.machinery
import json
import unittest
from pathlib import Path

OV = importlib.machinery.SourceFileLoader("ov_up", "bin/ov-up").load_module()
COMPOSE = Path("openviking/docker-compose.yml").read_text()
TEMPLATE = Path("openviking/ov.conf.template").read_text()


class OpenVikingConfig(unittest.TestCase):
    def test_image_is_pinned(self):
        self.assertIn("image: ghcr.io/volcengine/openviking:v0.4.19", COMPOSE)

    def test_port_bound_to_localhost(self):
        self.assertIn('"127.0.0.1:1933:1933"', COMPOSE)

    def test_models(self):
        conf = json.loads(OV.render_config(TEMPLATE, {"OPENVIKING_ROOT_KEY": "x", "DEEPSEEK_API_KEY": "y"}))
        self.assertEqual(conf["embedding"]["dense"]["model"], "bge-m3")
        self.assertEqual(conf["vlm"]["model"], "deepseek-flash")
        self.assertEqual(conf["vlm"]["api_base"], "https://api.deepseek.com")

    def test_no_zai_subscription_key(self):
        for f in Path("openviking").iterdir():
            text = f.read_text()
            self.assertNotIn("ZHIPU", text)
            self.assertNotIn("zai", text.lower())

    def test_env_parsing(self):
        tmp = Path("tests/.tmp-env")
        tmp.write_text("# comment\nA=1\nB = two\n")
        try:
            self.assertEqual(OV.read_env(tmp), {"A": "1", "B": "two"})
        finally:
            tmp.unlink()


if __name__ == "__main__":
    unittest.main()
