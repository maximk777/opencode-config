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
from wslib.profiles import KNOWN_GATES, STAGES, from_column, load_profiles, resolve_profile, validate_profile

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


BREAKDOWN = {
    "title": "Breakdown of",
    "note": "Generated by tools/generate.py from stories/*/story.md. Do not edit.",
    "columns": ["Story", "Wave", "Scope", "Unmapped", "Tracker", "Depends"],
}


class BreakdownBlockTest(unittest.TestCase):
    def with_breakdown(self, **changes):
        data = checklist()
        block = copy.deepcopy(BREAKDOWN)
        block.update(changes)
        data["breakdown"] = block
        return data

    def assert_breakdown_error(self, data):
        findings = validate_profile(data, REL, "checklist")
        self.assertTrue(findings, "expected a breakdown finding")
        for f in findings:
            self.assertEqual((f.path, f.line, f.rule), (REL, 1, "profile"), findings)
            self.assertTrue(f.message.startswith("breakdown:"), f.message)

    def test_valid_block(self):
        self.assertEqual(validate_profile(self.with_breakdown(), REL, "checklist"), [])

    def test_absent_block(self):
        self.assertNotIn("breakdown", checklist())
        self.assertEqual(validate_profile(checklist(), REL, "checklist"), [])

    def test_title_not_a_string(self):
        self.assert_breakdown_error(self.with_breakdown(title=["Breakdown of"]))

    def test_empty_note(self):
        self.assert_breakdown_error(self.with_breakdown(note=""))

    def test_five_columns(self):
        self.assert_breakdown_error(self.with_breakdown(columns=BREAKDOWN["columns"][:5]))

    def test_non_string_column(self):
        self.assert_breakdown_error(self.with_breakdown(columns=["Story", "Wave", "Scope", 4, "Tracker", "Depends"]))

    def test_block_not_an_object(self):
        data = checklist()
        data["breakdown"] = "Breakdown of"
        self.assert_breakdown_error(data)


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

    def test_workspace_profile_loads_like_kit_profile(self):
        data = checklist()
        data["name"] = "team-flow"
        self.write_json(".agents/profiles/team-flow/profile.json", data)
        profiles, findings = load_profiles(Context(self.root))
        self.assertEqual(findings, [])
        self.assertEqual(list(profiles), ["team-flow"])
        self.assertEqual(profiles["team-flow"], data)

    def test_no_profiles(self):
        self.assertEqual(load_profiles(Context(self.root)), ({}, []))


UI_REL = ".agents/profiles/ui-migration/profile.json"


def english_ui_migration():
    data = copy.deepcopy(UI_MIGRATION)
    data["map_doc"]["from_column"] = "From"
    data["breakdown"] = copy.deepcopy(BREAKDOWN)
    return data


def russian_ui_migration():
    data = english_ui_migration()
    data["elements"][0]["tables"][0] = {"heading": "Переходы", "columns": ["Действие", "Цель"], "keys": ["Цель"]}
    data["story"]["sections"] = ["Цель", "Объём", "Критерии приёмки", "Проверка", "Вне объёма", "Открытые вопросы"]
    # epic.sections has no ru key in LOCALIZED and stays English.
    data["map_doc"]["tables"][0] = {
        "heading": "Трасса legacy",
        "columns": ["Группа legacy", "Пункт legacy", "Маршрут legacy", "Цель"],
        "target": "Цель",
    }
    data["map_doc"]["from_column"] = "Откуда"
    data["stages"]["map"][2]["table"] = "Трасса legacy"
    data["stages"]["ready"][1]["section"] = "Открытые вопросы"
    data["breakdown"] = {
        "title": "Разбивка",
        "note": "Сгенерировано tools/generate.py из stories/*/story.md. Не редактировать.",
        "columns": ["Стори", "Волна", "Экраны", "Без экрана", "Трекер", "Зависит от"],
    }
    return data


LOCALIZABLE = [
    ("elements", 0, "tables", 0, "heading"),
    ("elements", 0, "tables", 0, "columns"),
    ("elements", 0, "tables", 0, "keys"),
    ("story", "sections"),
    ("epic", "sections"),
    ("map_doc", "tables", 0, "heading"),
    ("map_doc", "tables", 0, "columns"),
    ("map_doc", "tables", 0, "target"),
    ("map_doc", "from_column"),
    ("stages", "map", 2, "table"),
    ("stages", "ready", 1, "section"),
    ("breakdown", "title"),
    ("breakdown", "note"),
    ("breakdown", "columns"),
]


def get_path(data, path):
    for step in path:
        data = data[step]
    return data


def set_path(data, path, value):
    get_path(data, path[:-1])[path[-1]] = value


def field_name(path):
    name = ""
    for step in path:
        name += "[%d]" % step if isinstance(step, int) else ("." if name else "") + step
    return name


def localized_ui_migration():
    en, ru = english_ui_migration(), russian_ui_migration()
    data = english_ui_migration()
    for path in LOCALIZABLE:
        value = {"en": get_path(en, path)}
        if path != ("epic", "sections"):
            value["ru"] = get_path(ru, path)
        set_path(data, path, value)
    return data


def with_summary(value):
    data = localized_ui_migration()
    data["story"]["summary_section"] = value
    return data


class ProfileFilesTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()

    def tearDown(self):
        self._tmp.cleanup()

    def write_json(self, rel, data):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def load(self, profile, kit=None):
        self.write_json(UI_REL, profile)
        if kit is not None:
            self.write_json(".agents/kit.json", kit)
        return load_profiles(Context(self.root))

    def messages(self, data):
        findings = validate_profile(data, UI_REL, "ui-migration")
        for f in findings:
            self.assertEqual((f.path, f.line, f.rule), (UI_REL, 1, "profile"), findings)
        return [f.message for f in findings]


class LocalizedProfileTest(ProfileFilesTest):
    def test_localized_profile_is_valid(self):
        self.assertEqual(self.messages(localized_ui_migration()), [])

    def test_resolves_to_workspace_language(self):
        profiles, findings = self.load(localized_ui_migration(), {"name": "workspace", "params": {"language": "ru"}})
        self.assertEqual(findings, [])
        self.assertEqual(profiles["ui-migration"], russian_ui_migration())

    def test_falls_back_to_en_without_language_key(self):
        profiles, _ = self.load(localized_ui_migration(), {"name": "workspace", "params": {"language": "ru"}})
        self.assertEqual(profiles["ui-migration"]["epic"]["sections"], UI_MIGRATION["epic"]["sections"])

    def test_english_without_kit_json(self):
        profiles, findings = self.load(localized_ui_migration())
        self.assertEqual(findings, [])
        self.assertEqual(profiles["ui-migration"], english_ui_migration())

    def test_english_without_language_param(self):
        profiles, _ = self.load(localized_ui_migration(), {"name": "workspace", "params": {"title": "W"}})
        self.assertEqual(profiles["ui-migration"], english_ui_migration())

    def test_invalid_language_means_en(self):
        for language in ("RU", "rus", 7, ["ru"], "ru\n"):
            profiles, findings = self.load(localized_ui_migration(), {"params": {"language": language}})
            self.assertEqual(findings, [])
            self.assertEqual(profiles["ui-migration"], english_ui_migration(), language)

    def test_plain_profile_loads_unchanged_in_other_language(self):
        profiles, findings = self.load(english_ui_migration(), {"params": {"language": "ru"}})
        self.assertEqual(findings, [])
        self.assertEqual(profiles["ui-migration"], english_ui_migration())

    def test_language_object_without_en_names_the_field(self):
        for path in LOCALIZABLE:
            data = localized_ui_migration()
            set_path(data, path, {"ru": get_path(russian_ui_migration(), path)})
            self.assertEqual(self.messages(data), ["%s: language object needs en" % field_name(path)], path)

    def test_malformed_language_keys(self):
        for keys in ({"en": "Transitions", "rus": "Переходы"}, {"en": "Transitions", "RU": "Переходы"}, {}):
            data = localized_ui_migration()
            data["elements"][0]["tables"][0]["heading"] = keys
            self.assertEqual(self.messages(data), ["elements[0].tables[0].heading: language object needs en"], keys)

    def test_language_value_of_wrong_type(self):
        cases = [
            (("elements", 0, "tables", 0, "heading"), {"en": "Transitions", "ru": ["Переходы"]}),
            (("story", "sections"), {"en": ["Goal"], "ru": "Цель"}),
            (("stages", "map", 2, "table"), {"en": "Legacy trace", "ru": 3}),
            (("breakdown", "columns"), {"en": BREAKDOWN["columns"], "ru": ["Стори"]}),
            (("breakdown", "note"), {"en": BREAKDOWN["note"], "ru": ""}),
        ]
        for path, value in cases:
            data = localized_ui_migration()
            set_path(data, path, value)
            self.assertTrue(self.messages(data), path)

    def test_language_object_in_non_localizable_field(self):
        cases = [
            (("name",), {"en": "ui-migration"}),
            (("elements", 0, "kind"), {"en": "screen", "ru": "экран"}),
            (("elements", 0, "prefix"), {"en": "screen"}),
            (("elements", 0, "dir"), {"en": "map", "ru": "карта"}),
            (("elements", 0, "fields"), {"en": UI_MIGRATION["elements"][0]["fields"]}),
            (("elements", 0, "may_be_empty"), {"en": ["parent"]}),
            (("elements", 0, "values", "kind"), {"en": ["place"]}),
            (("story", "fields"), {"en": UI_MIGRATION["story"]["fields"], "ru": ["ключ"]}),
            (("map_doc", "tables", 0, "keys"), {"en": ["Target"]}),
            (("stages", "goal", 0, "gate"), {"en": "epic_sections"}),
        ]
        for path, value in cases:
            data = localized_ui_migration()
            set_path(data, path, value)
            self.assertTrue(self.messages(data), path)

    def test_language_object_in_element_table_target(self):
        data = localized_ui_migration()
        data["elements"][0]["tables"][0]["target"] = {"en": "Target"}
        self.assertTrue(self.messages(data))

    def test_resolution_does_not_mutate_the_loaded_profile(self):
        data = localized_ui_migration()
        before = copy.deepcopy(data)
        resolved = resolve_profile(data, "ru")
        self.assertEqual(data, before)
        self.assertEqual(resolved, russian_ui_migration())

    def test_summary_section_russian_workspace_gets_russian_value(self):
        profiles, findings = self.load(with_summary({"en": "Goal", "ru": "Цель"}), {"params": {"language": "ru"}})
        self.assertEqual(findings, [])
        self.assertEqual(profiles["ui-migration"]["story"]["summary_section"], "Цель")

    def test_summary_section_english_workspace_gets_english_value(self):
        profiles, findings = self.load(with_summary({"en": "Goal", "ru": "Цель"}))
        self.assertEqual(findings, [])
        self.assertEqual(profiles["ui-migration"]["story"]["summary_section"], "Goal")

    def test_summary_section_plain_value_is_kept(self):
        profiles, findings = self.load(with_summary("Goal"), {"params": {"language": "ru"}})
        self.assertEqual(findings, [])
        self.assertEqual(profiles["ui-migration"]["story"]["summary_section"], "Goal")

    def test_summary_section_bad_value_is_a_finding(self):
        cases = [
            ("", ["story.summary_section must be a non-empty string"]),
            (3, ["story.summary_section must be a non-empty string"]),
            (["Goal"], ["story.summary_section must be a non-empty string"]),
            ({"en": "Goal", "ru": 3}, ["story.summary_section must be a non-empty string"]),
            ({"ru": "Цель"}, ["story.summary_section: language object needs en"]),
            ({"en": "Goal", "rus": "Цель"}, ["story.summary_section: language object needs en"]),
        ]
        for value, expected in cases:
            self.assertEqual(self.messages(with_summary(value)), expected, value)

    def test_profile_without_summary_section_is_unchanged(self):
        profiles, findings = self.load(localized_ui_migration(), {"params": {"language": "ru"}})
        self.assertEqual(findings, [])
        self.assertNotIn("summary_section", profiles["ui-migration"]["story"])
        self.assertEqual(profiles["ui-migration"], russian_ui_migration())


def with_from_column(value):
    data = localized_ui_migration()
    data["map_doc"]["from_column"] = value
    return data


class FromColumnTest(ProfileFilesTest):
    def test_russian_workspace_gets_russian_value(self):
        profiles, findings = self.load(with_from_column({"en": "From", "ru": "Откуда"}), {"params": {"language": "ru"}})
        self.assertEqual(findings, [])
        self.assertEqual(profiles["ui-migration"]["map_doc"]["from_column"], "Откуда")
        self.assertEqual(from_column(profiles["ui-migration"]), "Откуда")

    def test_english_workspace_gets_english_value(self):
        profiles, findings = self.load(with_from_column({"en": "From", "ru": "Откуда"}))
        self.assertEqual(findings, [])
        self.assertEqual(from_column(profiles["ui-migration"]), "From")

    def test_plain_value_is_kept(self):
        profiles, findings = self.load(with_from_column("Source"), {"params": {"language": "ru"}})
        self.assertEqual(findings, [])
        self.assertEqual(from_column(profiles["ui-migration"]), "Source")

    def test_absent_value_defaults_to_from(self):
        data = localized_ui_migration()
        del data["map_doc"]["from_column"]
        profiles, findings = self.load(data, {"params": {"language": "ru"}})
        self.assertEqual(findings, [])
        self.assertNotIn("from_column", profiles["ui-migration"]["map_doc"])
        self.assertEqual(from_column(profiles["ui-migration"]), "From")
        self.assertEqual(from_column(checklist()), "From")
        without_map_doc = checklist()
        del without_map_doc["map_doc"]
        self.assertEqual(from_column(without_map_doc), "From")

    def test_bad_value_is_a_finding(self):
        cases = [
            ("", ["map_doc.from_column must be a non-empty string"]),
            (3, ["map_doc.from_column must be a non-empty string"]),
            (["From"], ["map_doc.from_column must be a non-empty string"]),
            ({"en": "From", "ru": ""}, ["map_doc.from_column must be a non-empty string"]),
            ({"ru": "Откуда"}, ["map_doc.from_column: language object needs en"]),
            ({"en": "From", "rus": "Откуда"}, ["map_doc.from_column: language object needs en"]),
        ]
        for value, expected in cases:
            self.assertEqual(self.messages(with_from_column(value)), expected, value)


if __name__ == "__main__":
    unittest.main()
