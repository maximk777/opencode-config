import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kits/workspace/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import copy
import json
import tempfile
import unittest

from wslib.common import Context
from wslib.profiles import KNOWN_GATES, STAGES, load_profiles, validate_profile

FIXTURE = Path(__file__).resolve().parent / "fixtures/profiles/checklist/profile.json"
REL = ".agents/profiles/checklist/profile.json"

UI_MIGRATION = {
    "name": "ui-migration",
    "elements": [
        {
            "kind": "screen",
            "prefix": "screen",
            "dir": "map",
            "fields": ["key", "route", "kind", "section", "parent", "access", "label", "wave", "story"],
            "may_be_empty": ["parent", "story"],
            "values": {"kind": ["place"]},
            "tables": [{"heading": "Transitions", "columns": ["Action", "Target"], "keys": ["Target"]}],
        }
    ],
    "story": {
        "fields": ["key", "type", "wave", "tracker", "scope", "depends", "repos", "decisions", "mockups"],
        "may_be_empty": ["tracker", "scope", "depends", "repos", "decisions", "mockups"],
        "values": {"type": ["story"]},
        "sections": ["Goal", "Scope", "Acceptance criteria", "Verification", "Out of scope", "Open questions"],
    },
    "epic": {
        "sections": ["Goal", "Scope", "Success criteria", "Out of scope", "Open questions", "Target users", "Product"]
    },
    "map_doc": {
        "tables": [
            {
                "heading": "Legacy trace",
                "columns": ["Legacy group", "Legacy item", "Legacy route", "Target"],
                "target": "Target",
            }
        ]
    },
    "stages": {
        "goal": [{"gate": "epic_sections"}, {"gate": "approval"}],
        "map": [
            {"gate": "unique_keys"},
            {"gate": "no_dangling_targets"},
            {"gate": "legacy_traced", "table": "Legacy trace"},
            {"gate": "approval"},
        ],
        "decomposition": [{"gate": "two_way_coverage"}, {"gate": "approval"}],
        "ready": [{"gate": "tracker_ids"}, {"gate": "no_open_questions", "section": "Open questions"}],
        "delivery": [],
        "done": [{"gate": "work_records"}],
    },
}


def checklist():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class ConstantsTest(unittest.TestCase):
    def test_stages(self):
        self.assertEqual(STAGES, ["goal", "map", "decomposition", "ready", "delivery", "done"])

    def test_known_gates(self):
        self.assertEqual(
            {name: sorted(params) for name, params in KNOWN_GATES.items()},
            {
                "approval": [],
                "epic_sections": [],
                "unique_keys": [],
                "no_dangling_targets": [],
                "legacy_traced": ["table"],
                "two_way_coverage": [],
                "tracker_ids": [],
                "no_open_questions": ["section"],
                "work_records": [],
            },
        )


class ValidateProfileTest(unittest.TestCase):
    def assert_profile_error(self, data, folder="checklist"):
        findings = validate_profile(data, REL, folder)
        self.assertTrue(findings, "expected a profile finding")
        for f in findings:
            self.assertEqual((f.path, f.line, f.rule), (REL, 1, "profile"), findings)
        return findings

    def test_checklist_fixture_is_valid(self):
        self.assertEqual(validate_profile(checklist(), REL, "checklist"), [])

    def test_ui_migration_example_is_valid(self):
        rel = ".agents/profiles/ui-migration/profile.json"
        self.assertEqual(validate_profile(copy.deepcopy(UI_MIGRATION), rel, "ui-migration"), [])

    def test_unknown_gate(self):
        data = checklist()
        data["stages"]["map"].append({"gate": "magic_gate"})
        findings = self.assert_profile_error(data)
        self.assertIn("magic_gate", " ".join(f.message for f in findings))

    def test_gate_without_name(self):
        data = checklist()
        data["stages"]["map"].append({"table": "Checks"})
        self.assert_profile_error(data)

    def test_gate_not_an_object(self):
        data = checklist()
        data["stages"]["map"].append("unique_keys")
        self.assert_profile_error(data)

    def test_unknown_parameter(self):
        data = checklist()
        data["stages"]["ready"][1]["depth"] = 2
        findings = self.assert_profile_error(data)
        self.assertIn("depth", " ".join(f.message for f in findings))

    def test_parameter_of_another_gate(self):
        data = checklist()
        data["stages"]["goal"][1]["table"] = "Checks"
        self.assert_profile_error(data)

    def test_missing_stage(self):
        data = checklist()
        del data["stages"]["delivery"]
        findings = self.assert_profile_error(data)
        self.assertIn("delivery", " ".join(f.message for f in findings))

    def test_unknown_stage(self):
        data = checklist()
        data["stages"]["review"] = []
        findings = self.assert_profile_error(data)
        self.assertIn("review", " ".join(f.message for f in findings))

    def test_stages_not_an_object(self):
        data = checklist()
        data["stages"] = []
        self.assert_profile_error(data)

    def test_stage_not_a_list(self):
        data = checklist()
        data["stages"]["done"] = {"gate": "work_records"}
        self.assert_profile_error(data)

    def test_name_differs_from_folder(self):
        self.assert_profile_error(checklist(), folder="other")

    def test_missing_name(self):
        data = checklist()
        del data["name"]
        self.assert_profile_error(data)

    def test_non_string_name(self):
        data = checklist()
        data["name"] = 7
        self.assert_profile_error(data)

    def test_not_an_object(self):
        self.assert_profile_error([])

    def test_elements_not_a_list(self):
        data = checklist()
        data["elements"] = data["elements"][0]
        self.assert_profile_error(data)

    def test_element_not_an_object(self):
        data = checklist()
        data["elements"] = ["rule"]
        self.assert_profile_error(data)

    def test_element_without_string_kind_prefix_dir(self):
        for field in ("kind", "prefix", "dir"):
            data = checklist()
            data["elements"][0][field] = ["rules"]
            self.assert_profile_error(data)
            data = checklist()
            del data["elements"][0][field]
            self.assert_profile_error(data)

    def test_element_fields_not_a_list(self):
        data = checklist()
        data["elements"][0]["fields"] = "key, owner, story"
        self.assert_profile_error(data)

    def test_element_may_be_empty_not_a_list(self):
        data = checklist()
        data["elements"][0]["may_be_empty"] = "story"
        self.assert_profile_error(data)

    def test_element_tables_not_a_list(self):
        data = checklist()
        data["elements"][0]["tables"] = {"heading": "Checks"}
        self.assert_profile_error(data)

    def test_story_fields_not_a_list(self):
        data = checklist()
        data["story"]["fields"] = "key"
        self.assert_profile_error(data)

    def test_story_sections_not_a_list(self):
        data = checklist()
        data["story"]["sections"] = "Goal"
        self.assert_profile_error(data)

    def test_story_missing(self):
        data = checklist()
        del data["story"]
        self.assert_profile_error(data)

    def test_epic_sections_not_a_list(self):
        data = checklist()
        data["epic"]["sections"] = "Goal"
        self.assert_profile_error(data)

    def test_map_doc_tables_not_a_list(self):
        data = checklist()
        data["map_doc"]["tables"] = "Legacy trace"
        self.assert_profile_error(data)


class LoadProfilesTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def write_json(self, rel, data):
        self.write(rel, json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    def test_keeps_valid_profiles_by_name(self):
        self.write_json(".agents/profiles/checklist/profile.json", checklist())
        self.write_json(".agents/profiles/ui-migration/profile.json", UI_MIGRATION)
        profiles, findings = load_profiles(Context(self.root))
        self.assertEqual(findings, [])
        self.assertEqual(sorted(profiles), ["checklist", "ui-migration"])
        self.assertEqual(profiles["checklist"], checklist())

    def test_invalid_profile_is_absent_and_reported(self):
        data = checklist()
        data["stages"]["map"].append({"gate": "magic_gate"})
        self.write_json(".agents/profiles/checklist/profile.json", data)
        self.write_json(".agents/profiles/ui-migration/profile.json", UI_MIGRATION)
        profiles, findings = load_profiles(Context(self.root))
        self.assertEqual(sorted(profiles), ["ui-migration"])
        self.assertTrue(findings)
        for f in findings:
            self.assertEqual((f.path, f.line, f.rule), (REL, 1, "profile"))

    def test_invalid_json_is_a_finding(self):
        self.write(REL, '{"name": "checklist",\n')
        profiles, findings = load_profiles(Context(self.root))
        self.assertEqual(profiles, {})
        self.assertEqual(len(findings), 1, findings)
        self.assertEqual((findings[0].path, findings[0].line, findings[0].rule), (REL, 1, "profile"))

    def test_ignores_other_files(self):
        self.write_json(".agents/profiles/checklist/profile.json", checklist())
        self.write(".agents/profiles/checklist/story.md", "# Story\n")
        self.write_json(".agents/profiles/profile.json", {"name": "loose"})
        self.write_json(".agents/profiles/a/b/profile.json", {"name": "b"})
        profiles, findings = load_profiles(Context(self.root))
        self.assertEqual(findings, [])
        self.assertEqual(list(profiles), ["checklist"])

    def test_no_profiles(self):
        self.assertEqual(load_profiles(Context(self.root)), ({}, []))


if __name__ == "__main__":
    unittest.main()
