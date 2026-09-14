"""Stream profiles: loading and shape validation of .agents/profiles/<name>/profile.json."""
from __future__ import annotations

import posixpath
from typing import Dict, List, Tuple

from wslib.common import Finding

RULE = "profile"
PROFILES_DIR = ".agents/profiles"
STAGES = ["goal", "map", "decomposition", "ready", "delivery", "done"]
KNOWN_GATES = {
    "approval": (),
    "epic_sections": (),
    "unique_keys": (),
    "no_dangling_targets": (),
    "legacy_traced": ("table",),
    "two_way_coverage": (),
    "tracker_ids": (),
    "no_open_questions": ("section",),
    "work_records": (),
}


def _is_str_list(value) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _check_tables(value, where: str, problems: List[str]) -> None:
    if not isinstance(value, list):
        problems.append("%s must be a list" % where)
        return
    for i, table in enumerate(value):
        label = "%s[%d]" % (where, i)
        if not isinstance(table, dict):
            problems.append("%s must be an object" % label)
            continue
        if not isinstance(table.get("heading"), str):
            problems.append("%s.heading must be a string" % label)
        if not _is_str_list(table.get("columns")):
            problems.append("%s.columns must be a list of strings" % label)
        if "keys" in table and not _is_str_list(table["keys"]):
            problems.append("%s.keys must be a list of strings" % label)
        if "target" in table and not isinstance(table["target"], str):
            problems.append("%s.target must be a string" % label)


def _check_values(value, where: str, problems: List[str]) -> None:
    if not isinstance(value, dict) or not all(_is_str_list(v) for v in value.values()):
        problems.append("%s must be an object of string lists" % where)


def _check_elements(data: dict, problems: List[str]) -> None:
    elements = data.get("elements")
    if not isinstance(elements, list):
        problems.append("elements must be a list")
        return
    for i, element in enumerate(elements):
        label = "elements[%d]" % i
        if not isinstance(element, dict):
            problems.append("%s must be an object" % label)
            continue
        for field in ("kind", "prefix", "dir"):
            if not isinstance(element.get(field), str):
                problems.append("%s.%s must be a string" % (label, field))
        if not _is_str_list(element.get("fields")):
            problems.append("%s.fields must be a list of strings" % label)
        if "may_be_empty" in element and not _is_str_list(element["may_be_empty"]):
            problems.append("%s.may_be_empty must be a list of strings" % label)
        if "values" in element:
            _check_values(element["values"], label + ".values", problems)
        if "tables" in element:
            _check_tables(element["tables"], label + ".tables", problems)


def _check_story(data: dict, problems: List[str]) -> None:
    story = data.get("story")
    if not isinstance(story, dict):
        problems.append("story must be an object")
        return
    for field in ("fields", "sections"):
        if not _is_str_list(story.get(field)):
            problems.append("story.%s must be a list of strings" % field)
    if "may_be_empty" in story and not _is_str_list(story["may_be_empty"]):
        problems.append("story.may_be_empty must be a list of strings")
    if "values" in story:
        _check_values(story["values"], "story.values", problems)


def _check_optional_docs(data: dict, problems: List[str]) -> None:
    if "epic" in data:
        epic = data["epic"]
        if not isinstance(epic, dict) or not _is_str_list(epic.get("sections")):
            problems.append("epic.sections must be a list of strings")
    if "map_doc" in data:
        map_doc = data["map_doc"]
        if not isinstance(map_doc, dict):
            problems.append("map_doc must be an object")
        else:
            _check_tables(map_doc.get("tables"), "map_doc.tables", problems)


def _check_stages(data: dict, problems: List[str]) -> None:
    stages = data.get("stages")
    if not isinstance(stages, dict):
        problems.append("stages must be an object")
        return
    for stage in STAGES:
        if stage not in stages:
            problems.append("stages: missing stage %s" % stage)
    for stage, gates in stages.items():
        if stage not in STAGES:
            problems.append("stages: unknown stage %s" % stage)
            continue
        if not isinstance(gates, list):
            problems.append("stages.%s must be a list" % stage)
            continue
        for i, gate in enumerate(gates):
            label = "stages.%s[%d]" % (stage, i)
            if not isinstance(gate, dict):
                problems.append("%s must be an object" % label)
                continue
            name = gate.get("gate")
            if not isinstance(name, str) or name not in KNOWN_GATES:
                problems.append("%s: unknown gate %s" % (label, name))
                continue
            for param in gate:
                if param != "gate" and param not in KNOWN_GATES[name]:
                    problems.append("%s: gate %s has unknown parameter %s" % (label, name, param))


def validate_profile(data, rel: str, folder_name: str) -> List[Finding]:
    """Return one `profile` finding per shape problem of a parsed profile.json."""
    if not isinstance(data, dict):
        return [Finding(rel, 1, RULE, "profile must be a JSON object")]
    problems: List[str] = []
    name = data.get("name")
    if not isinstance(name, str):
        problems.append("name must be a string")
    elif name != folder_name:
        problems.append("name %s differs from folder %s" % (name, folder_name))
    _check_elements(data, problems)
    _check_story(data, problems)
    _check_optional_docs(data, problems)
    _check_stages(data, problems)
    return [Finding(rel, 1, RULE, problem) for problem in problems]


def load_profiles(ctx) -> Tuple[Dict[str, dict], List[Finding]]:
    """Read every .agents/profiles/<name>/profile.json; invalid profiles are left out and reported."""
    profiles: Dict[str, dict] = {}
    findings: List[Finding] = []
    for rel in ctx.files:
        folder = posixpath.dirname(rel)
        if posixpath.basename(rel) != "profile.json" or posixpath.dirname(folder) != PROFILES_DIR:
            continue
        data, error = ctx.load_json(rel)
        if error is not None:
            findings.append(Finding(rel, 1, RULE, error.message))
            continue
        problems = validate_profile(data, rel, posixpath.basename(folder))
        if problems:
            findings.extend(problems)
            continue
        profiles[data["name"]] = data
    return profiles, findings
