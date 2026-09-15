import unittest
from pathlib import Path

REPO = Path(".").resolve()

# Markers assembled from fragments so this file never contains one literally.
_MARKERS = [
    "wild" + "berries",
    "rw" + "b.ru",
    "wb" + "bank",
    "abs-" + "arm",
    "kiri" + "enkov",
    "super" + "office",
    "stage-" + "el",
]


class PublicFiles(unittest.TestCase):
    def test_readme_exists_and_names_commands(self):
        readme = (REPO / "README.md").read_text()
        for needle in ["bin/claude-link", "bin/ov-up", "bin/check-public", "node --test", "python3 -m unittest"]:
            self.assertIn(needle, readme)

    def test_license_is_mit_for_public_identity(self):
        license_text = (REPO / "LICENSE").read_text()
        self.assertIn("MIT License", license_text)
        self.assertIn("maximk777", license_text)

    def test_public_files_carry_no_marker(self):
        for name in ["README.md", "LICENSE"]:
            text = (REPO / name).read_text().lower()
            for marker in _MARKERS:
                self.assertNotIn(marker.lower(), text, f"{name} contains marker")


if __name__ == "__main__":
    unittest.main()
