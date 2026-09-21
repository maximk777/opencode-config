"""Stream profiles: loading and shape validation of .agents/profiles/<name>/profile.json."""
from __future__ import annotations

import copy
import posixpath
import re
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
LANGUAGE_RE = re.compile(r"[a-z]{2}")
DEFAULT_LANGUAGE = "en"
DEFAULT_FROM_COLUMN = "From"


def _is_str(value) -> bool:
    return isinstance(value, str)


def _is_str_list(value) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _variants(value, where: str, problems: List[str]) -> list:
    """Values to type-check for a localizable field: each language's value, or the plain value itself."""
    if not isinstance(value, dict):
        return [value]
    if DEFAULT_LANGUAGE not in value or not all(isinstance(k, str) and LANGUAGE_RE.fullmatch(k) for k in value):
        problems.append("%s: language object needs en" % where)
        return []
    return list(value.values())


def _localized_ok(value, where: str, problems: List[str], check) -> bool:
    return all(check(v) for v in _variants(value, where, problems))


def _check_tables(value, where: str, problems: List[str], localized_extra: str) -> None:
    """localized_extra names the one optional field (keys or target) that is localizable in this table list."""
    if not isinstance(value, list):
        problems.append("%s must be a list" % where)
        return
    for i, table in enumerate(value):
        label = "%s[%d]" % (where, i)
        if not isinstance(table, dict):
            problems.append("%s must be an object" % label)
            continue
        for field, check, kind, required in (
            ("heading", _is_str, "a string", True),
            ("columns", _is_str_list, "a list of strings", True),
            ("keys", _is_str_list, "a list of strings", False),
            ("target", _is_str, "a string", False),
        ):
            if not required and field not in table:
                continue
            value, name = table.get(field), "%s.%s" % (label, field)
            if field in ("heading", "columns", localized_extra):
                ok = _localized_ok(value, name, problems, check)
            else:
                ok = check(value)
            if not ok:
                problems.append("%s must be %s" % (name, kind))


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
            _check_tables(element["tables"], label + ".tables", problems, "keys")


def _check_story(data: dict, problems: List[str]) -> None:
    story = data.get("story")
    if not isinstance(story, dict):
        problems.append("story must be an object")
        return
    if not _is_str_list(story.get("fields")):
        problems.append("story.fields must be a list of strings")
    if not _localized_ok(story.get("sections"), "story.sections", problems, _is_str_list):
        problems.append("story.sections must be a list of strings")
    if "summary_section" in story and not _localized_ok(story["summary_section"], "story.summary_section", problems, _is_text):
        problems.append("story.summary_section must be a non-empty string")
    if "may_be_empty" in story and not _is_str_list(story["may_be_empty"]):
        problems.append("story.may_be_empty must be a list of strings")
    if "values" in story:
        _check_values(story["values"], "story.values", problems)


def _check_optional_docs(data: dict, problems: List[str]) -> None:
    if "epic" in data:
        epic = data["epic"]
        if not isinstance(epic, dict) or not _localized_ok(epic.get("sections"), "epic.sections", problems, _is_str_list):
            problems.append("epic.sections must be a list of strings")
    if "map_doc" in data:
        map_doc = data["map_doc"]
        if not isinstance(map_doc, dict):
            problems.append("map_doc must be an object")
        else:
            _check_tables(map_doc.get("tables"), "map_doc.tables", problems, "target")
            if "from_column" in map_doc and not _localized_ok(
                map_doc["from_column"], "map_doc.from_column", problems, _is_text
            ):
                problems.append("map_doc.from_column must be a non-empty string")


def _is_text(value) -> bool:
    return isinstance(value, str) and value != ""


def _check_breakdown(data: dict, problems: List[str]) -> None:
    if "breakdown" not in data:
        return
    block = data["breakdown"]
    if not isinstance(block, dict):
        problems.append("breakdown: must be an object")
        return
    for field in ("title", "note"):
        if not _localized_ok(block.get(field), "breakdown." + field, problems, _is_text):
            problems.append("breakdown: %s must be a non-empty string" % field)

    def six_texts(columns) -> bool:
        return isinstance(columns, list) and len(columns) == 6 and all(_is_text(c) for c in columns)

    if not _localized_ok(block.get("columns"), "breakdown.columns", problems, six_texts):
        problems.append("breakdown: columns must be a list of 6 non-empty strings")


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
                if param == "gate":
                    continue
                if param not in KNOWN_GATES[name]:
                    problems.append("%s: gate %s has unknown parameter %s" % (label, name, param))
                # Every known gate parameter (table, section) is localizable; plain values keep their old, unchecked type.
                elif isinstance(gate[param], dict):
                    where = "%s.%s" % (label, param)
                    if not _localized_ok(gate[param], where, problems, _is_str):
                        problems.append("%s must be a string" % where)


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
    _check_breakdown(data, problems)
    _check_stages(data, problems)
    return [Finding(rel, 1, RULE, problem) for problem in problems]


def _pick(value, language: str):
    if isinstance(value, dict):
        return value.get(language, value[DEFAULT_LANGUAGE])
    return value


def resolve_profile(data: dict, language: str) -> dict:
    """Return a copy of a valid profile with every localizable field resolved to language, falling back to en."""
    resolved = copy.deepcopy(data)
    tables = [table for element in resolved["elements"] for table in element.get("tables", [])]
    tables += resolved.get("map_doc", {}).get("tables", [])
    for table in tables:
        for field in ("heading", "columns", "keys", "target"):
            if field in table:
                table[field] = _pick(table[field], language)
    for doc in ("story", "epic"):
        if doc in resolved:
            resolved[doc]["sections"] = _pick(resolved[doc]["sections"], language)
    if "from_column" in resolved.get("map_doc", {}):
        resolved["map_doc"]["from_column"] = _pick(resolved["map_doc"]["from_column"], language)
    if "story" in resolved and "summary_section" in resolved["story"]:
        resolved["story"]["summary_section"] = _pick(resolved["story"]["summary_section"], language)
    if "breakdown" in resolved:
        for field in ("title", "note", "columns"):
            resolved["breakdown"][field] = _pick(resolved["breakdown"][field], language)
    for gates in resolved["stages"].values():
        for gate in gates:
            for param in gate:
                if param != "gate":
                    gate[param] = _pick(gate[param], language)
    return resolved


def from_column(profile: dict) -> str:
    """First column of the generated element tables of a resolved profile; From when absent."""
    return profile.get("map_doc", {}).get("from_column", DEFAULT_FROM_COLUMN)


def workspace_language(ctx) -> str:
    """params.language of .agents/kit.json; en when absent or invalid."""
    language = ctx.kit_params().get("language")
    if isinstance(language, str) and LANGUAGE_RE.fullmatch(language):
        return language
    return DEFAULT_LANGUAGE


def load_profiles(ctx) -> Tuple[Dict[str, dict], List[Finding]]:
    """Read every .agents/profiles/<name>/profile.json; invalid profiles are left out and reported."""
    profiles: Dict[str, dict] = {}
    findings: List[Finding] = []
    language = workspace_language(ctx)
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
        profiles[data["name"]] = resolve_profile(data, language)
    return profiles, findings
