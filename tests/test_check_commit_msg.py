import importlib.machinery
import unittest

C = importlib.machinery.SourceFileLoader("ccm", "bin/check-commit-msg").load_module()


class CommitMessage(unittest.TestCase):
    def test_valid_message(self):
        self.assertIsNone(C.check("feat(clients): add passport expiry check\n"))

    def test_missing_type_rejected(self):
        self.assertIsNotNone(C.check("Fix stuff"))

    def test_body_rejected(self):
        self.assertIn("body", C.check("fix(api): handle nil\n\nlonger explanation"))

    def test_trailer_rejected(self):
        self.assertIsNotNone(C.check("fix(api): handle nil\n\nCo-Authored-By: someone <a@b.c>"))

    def test_long_subject_rejected(self):
        self.assertIn("72", C.check("feat(x): " + "a" * 64))

    def test_capitalized_subject_rejected(self):
        self.assertIsNotNone(C.check("feat(x): Add thing"))

    def test_comment_lines_ignored(self):
        self.assertIsNone(C.check("chore(tiers): set fast to deepseek-flash\n# Please enter the commit message\n"))


if __name__ == "__main__":
    unittest.main()
