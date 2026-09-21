"""Rules: stream.json shape, profile validity and the gates of closed stages; plus the remaining work report."""
from __future__ import annotations

from typing import Dict, List, Tuple

from wslib.common import Finding
from wslib.model import Workspace
from wslib.predicates import PREDICATES
from wslib.profiles import PROFILES_DIR, STAGES

LIFECYCLE = "lifecycle"
PROFILE = "profile"
STAGE_GATE = "stage-gate"
SCOPE_PROBLEM = "scope must be a list of strings"

# check.py calls every rule with the same Context; one evaluation serves all three rules.
_CACHE: Dict[int, Tuple[object, Workspace, Dict[str, List[Finding]]]] = {}


def _is_str_list(value) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _shape_problems(stream) -> List[str]:
    data = stream.data
    problems: List[str] = []
    key = data.get("key")
    if not isinstance(key, str):
        problems.append("key must be the string %s" % stream.key)
    elif key != stream.key:
        problems.append("key %s does not match folder key %s" % (key, stream.key))
    if not isinstance(data.get("profile"), str):
        problems.append("profile must be a string")
    stage = data.get("stage")
    if not isinstance(stage, str):
        problems.append("stage must be a string")
    elif stage not in STAGES:
        problems.append("stage %s is not one of %s" % (stage, ", ".join(STAGES)))
    if not _is_str_list(data.get("scope")):
        problems.append(SCOPE_PROBLEM)
    marks = data.get("approvals")
    if not isinstance(marks, list):
        problems.append("approvals must be a list of objects with string stage, by and date")
        return problems
    current = STAGES.index(stage) if stage in STAGES else None
    for i, mark in enumerate(marks):
        if not isinstance(mark, dict) or not all(isinstance(mark.get(f), str) for f in ("stage", "by", "date")):
            problems.append("approvals[%d] must be an object with string stage, by and date" % i)
            continue
        if mark["stage"] not in STAGES:
            problems.append("approvals[%d] names unknown stage %s" % (i, mark["stage"]))
        elif current is not None and STAGES.index(mark["stage"]) > current:
            problems.append("approvals[%d] is for stage %s, later than current stage %s" % (i, mark["stage"], stage))
    return problems


def _gate_issues(ws, stream, profile, stage: str):
    """Yield (gate name, Issue) for every failure of the gates of one stage."""
    for gate in profile["stages"][stage]:
        name = gate["gate"]
        params = {k: v for k, v in gate.items() if k != "gate"}
        if name == "approval":
            params["stage"] = stage
        for issue in PREDICATES[name](ws, stream, profile, params):
            yield name, issue


def _checkable(ws, stream):
    """Return (profile, stage index) when the stream's gates can be evaluated, else None."""
    if stream.data is None or stream.profile_name not in ws.profiles:
        return None
    stage = stream.data.get("stage")
    if stage not in STAGES:
        return None
    return ws.profiles[stream.profile_name], STAGES.index(stage)


def _evaluate(ctx) -> Tuple[Workspace, Dict[str, List[Finding]]]:
    cached = _CACHE.get(id(ctx))
    if cached is not None and cached[0] is ctx:
        return cached[1], cached[2]
    ws = Workspace(ctx)
    results: Dict[str, List[Finding]] = {LIFECYCLE: [], PROFILE: list(ws.profile_findings), STAGE_GATE: []}
    for stream in ws.streams:
        if stream.error is not None:
            results[LIFECYCLE].append(stream.error)
            continue
        name = stream.profile_name
        if name is not None and name not in ws.profiles:
            # A present but invalid profile is already a `profile` finding; its streams get nothing more.
            if "%s/%s/profile.json" % (PROFILES_DIR, name) not in ctx.files:
                results[LIFECYCLE].append(Finding(stream.path, 1, LIFECYCLE, "unknown profile %s" % name))
            continue
        for problem in _shape_problems(stream):
            results[LIFECYCLE].append(Finding(stream.path, 1, LIFECYCLE, problem))
        scope = stream.data.get("scope")
        if _is_str_list(scope):
            for key in scope:
                if key not in ws.elements:
                    results[LIFECYCLE].append(
                        Finding(stream.path, 1, LIFECYCLE, "scope key %s names no map element" % key)
                    )
        found = _checkable(ws, stream)
        if found is None:
            continue
        profile, current = found
        for stage in STAGES[:current]:
            for gate, issue in _gate_issues(ws, stream, profile, stage):
                # two_way_coverage repeats the shape check of stream scope, which is already a lifecycle finding.
                if gate == "two_way_coverage" and issue.path == stream.path and issue.detail == SCOPE_PROBLEM:
                    continue
                results[STAGE_GATE].append(
                    Finding(issue.path, issue.line, STAGE_GATE, "%s %s: %s" % (stage, gate, issue.detail))
                )
    # Only the latest Context is kept, so the cache neither grows nor outlives a reused id.
    _CACHE.clear()
    _CACHE[id(ctx)] = (ctx, ws, results)
    return ws, results


def check_lifecycle(ctx) -> List[Finding]:
    return _evaluate(ctx)[1][LIFECYCLE]


def check_profiles(ctx) -> List[Finding]:
    return _evaluate(ctx)[1][PROFILE]


def check_stage_gates(ctx) -> List[Finding]:
    return _evaluate(ctx)[1][STAGE_GATE]


def remaining(ctx) -> List[str]:
    """Failures of the current stage's gates of every stream as `stream:<project>/<domain>/<stream> <stage> <gate>: path:line detail`."""
    ws = _evaluate(ctx)[0]
    lines: List[str] = []
    for stream in ws.streams:
        found = _checkable(ws, stream)
        if found is None:
            continue
        profile, current = found
        stage = STAGES[current]
        for gate, issue in _gate_issues(ws, stream, profile, stage):
            lines.append("%s %s %s: %s:%s %s" % (stream.key, stage, gate, issue.path, issue.line, issue.detail))
    return lines


RULES = [(LIFECYCLE, check_lifecycle), (PROFILE, check_profiles), (STAGE_GATE, check_stage_gates)]
