import importlib.machinery
import json
import unittest

G = importlib.machinery.SourceFileLoader("retrieval_gate", "bin/retrieval-gate").load_module()


class RetrievalGate(unittest.TestCase):
    def test_hits_only_in_top3(self):
        results = {
            "q1": ["viking://x/commit-message-style.md", "b", "c", "d"],
            "q2": ["a", "b", "c", "viking://x/opencode-migration.md"],
        }
        expected = {"q1": "commit-message-style", "q2": "opencode-migration"}
        self.assertEqual(G.score(results, expected), 1)

    def test_case_insensitive(self):
        self.assertEqual(G.score({"q": ["Memory/Commit-Message-Style"]}, {"q": "commit-message-style"}), 1)

    def test_verdict_tie_passes(self):
        self.assertEqual(G.verdict(15, 15), "GATE PASS")

    def test_verdict_lower_fails(self):
        self.assertEqual(G.verdict(11, 15), "GATE FAIL")

    def test_parse_queries(self):
        rows = G.parse_queries("# comment\nкак писать коммиты\tcommit-message-style\n\nopencode migration\topencode-migration\n")
        self.assertEqual(rows, [("как писать коммиты", "commit-message-style"), ("opencode migration", "opencode-migration")])

    def test_basic_memory_takes_top_three_results(self):
        out = "Searching...\n" + json.dumps({"results": [
            {"title": f"Note {i}", "permalink": f"memory/note-{i}", "file_path": f"note-{i}.md"} for i in range(1, 6)
        ], "current_page": 1})
        top3 = G.basic_memory_results(out)
        self.assertEqual(len(top3), 3)
        self.assertIn("memory/note-3", top3[2])
        self.assertEqual(G.score({"q": top3}, {"q": "note-3"}), 1)
        self.assertEqual(G.score({"q": top3}, {"q": "note-4"}), 0)

    def test_basic_memory_unparseable_output(self):
        self.assertEqual(G.basic_memory_results("error: project not found"), [])


if __name__ == "__main__":
    unittest.main()
