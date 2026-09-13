import importlib.machinery
import unittest

M = importlib.machinery.SourceFileLoader("memory_export", "bin/memory-export").load_module()


class MemoryExport(unittest.TestCase):
    def test_flags_jwt(self):
        self.assertTrue(M.find_secrets("token eyJfakeheaderAAAA.eyJfakepayloadBBBB.sig"))

    def test_flags_bearer(self):
        self.assertTrue(M.find_secrets("Authorization: Bearer abcdefghijklmnopqrstuvwxyz0123"))

    def test_flags_api_key_assignment(self):
        self.assertTrue(M.find_secrets("apiKey: abcdefghijklmnop"))

    def test_ignores_prose_about_tokens(self):
        self.assertFalse(M.find_secrets("token budget of 2000 for recall"))

    def test_triage_row_for_secret(self):
        rows = M.triage_rows([("memory/a.md", "Staging token", "Bearer abcdefghijklmnopqrstuvwxyz0123")])
        self.assertIn("| 1 | memory/a.md | Staging token | drop | contains secret |", rows)

    def test_triage_row_without_secret(self):
        rows = M.triage_rows([("memory/b.md", "Commit style", "Short commits")])
        self.assertIn("| 1 | memory/b.md | Commit style |  |  |", rows)


if __name__ == "__main__":
    unittest.main()
