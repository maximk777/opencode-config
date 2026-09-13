import importlib.machinery
import unittest

E = importlib.machinery.SourceFileLoader("error_background", "bin/error-background").load_module()

LOG = """aaaaaaa1\tfix(report): handle empty list
a.go

bbbbbbb2\tfeat: add b
b.go

ccccccc3\tRevert "feat: add b"
b.go

ddddddd4\thotfix null pointer
a.go
c.go
"""


class ErrorBackground(unittest.TestCase):
    def test_summary_counts(self):
        fixes, reverts, hot = E.summarize(E.parse(LOG))
        self.assertEqual(len(fixes), 2)
        self.assertEqual(len(reverts), 1)
        self.assertEqual(hot[0], ("a.go", 2, 2))

    def test_render(self):
        out = E.render("demo", E.parse(LOG))
        self.assertIn("Fix commits: 2", out)
        self.assertIn("| a.go | 2 | 2 |", out)

    def test_fix_keywords_match_whole_words(self):
        fixes = ["fix: x", "fix(api): x", "hotfix null pointer", "Bug in parser", "bugfix for login", "исправлен таймаут"]
        others = ["feat: add debug logging", "chore: remove debugger", "refactor: prefix handling", "docs: fixture notes"]
        for s in fixes:
            self.assertTrue(E.FIX.search(s), s)
        for s in others:
            self.assertFalse(E.FIX.search(s), s)


if __name__ == "__main__":
    unittest.main()
