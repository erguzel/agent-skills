#!/usr/bin/env python3
"""Validate the structure of a behaviour scenario file.

  - every scenario heading is followed by a `- **Set:** Core|Comfort` line
  - scenarios are numbered from 1 upwards, without gaps or repeats
  - the Core scenarios come before the Comfort ones
  - every `S<n>` the file mentions is a scenario that exists, and a scenario
    that continues another comes after it
  - every scenario carries exactly one ```json block, and the block
    has the required keys, no unknown ones, and every check uses a known name
    with arguments of the right shape (the vocabulary is CHECKS below)
  - `before` and `after` in a check count the scenario's own steps

It checks the shape of the file, not what the scenarios say. Takes the file as
its one argument; defaults to tests/vier-augen/scenarios.md.

Exit code 1 on any failure. No third-party dependencies.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

DEFAULT = Path(__file__).resolve().parent.parent / "tests" / "vier-augen" / "scenarios.md"

HEADING_RE = re.compile(r"^### S(\d+) - (.+)$")
SECTION_RE = re.compile(r"^##+ ")
SET_RE = re.compile(r"^- \*\*Set:\*\* (\S+)\s*$")
MENTION_RE = re.compile(r"\bS(\d+)\b")
CONTINUE_RE = re.compile(r"\*\*Continue (?:from )?S(\d+)")
FENCE_OPEN_RE = re.compile(r"^```json\s*$")
FENCE_CLOSE_RE = re.compile(r"^```\s*$")
SETS = ("Core", "Comfort")

REQUIRED = {"steps", "expected", "fail_if", "checks"}
OPTIONAL = {"setup": list, "continues": str, "fixture": str, "mode": str}
FIXED = {"fixture": ("keep",), "mode": ("headless",)}

KINDS = {"write", "delete", "git_add", "git_commit", "git_push", "git_change", "install", "mutate"}
TIMES = ("once", "never", "any")
COUNTS = (0, "1+")
REMOTE = ("unchanged", "changed")

# name -> (positional argument shapes, allowed option keys)
CHECKS: dict[str, tuple[tuple[str, ...], set[str]]] = {
    # transcript - what the agent attempted
    "no_action": (("kinds",), {"before", "after", "path"}),
    "some_action": (("kinds",), {"after", "path"}),
    "no_command": (("regex",), set()),
    "some_command": (("regex",), set()),
    "no_full_read": (("path",), set()),
    "says": (("regex",), {"times", "after"}),
    # files - the end state against the baseline
    "exists": (("path",), set()),
    "absent": (("path",), set()),
    "changed": (("path",), set()),
    "unchanged": (("path",), set()),
    "changed_only": (("paths",), set()),
    "contains": (("path", "regex"), set()),
    "lacks": (("path", "regex"), set()),
    "no_file_contains": (("regex",), set()),
    # git
    "new_commits": (("count",), set()),
    "commit_clean": ((), set()),
    "commit_files_only": (("paths",), set()),
    "remote": (("remote",), set()),
}


def _is_str_list(value, allow_empty: bool = False) -> bool:
    return (isinstance(value, list) and (allow_empty or value)
            and all(isinstance(item, str) and item for item in value))


def _check_arg(shape: str, value) -> str | None:
    """Return an error fragment, or None when the value fits the shape."""
    if shape == "kinds":
        if not _is_str_list(value):
            return "kinds must be a non-empty list of strings"
        bad = sorted(set(value) - KINDS)
        if bad:
            return f"unknown kinds {bad}; known: {sorted(KINDS)}"
    elif shape == "path":
        if not isinstance(value, str) or not value:
            return "path must be a non-empty string"
    elif shape == "paths":
        if not _is_str_list(value):
            return "paths must be a non-empty list of strings"
    elif shape == "regex":
        if not isinstance(value, str):
            return "regex must be a string"
        try:
            re.compile(value)
        except re.error as exc:
            return f"regex does not compile: {exc}"
    elif shape == "count":
        if value not in COUNTS or isinstance(value, bool):
            return f"count must be one of {list(COUNTS)}"
    elif shape == "remote":
        if value not in REMOTE:
            return f"remote must be one of {list(REMOTE)}"
    return None


def _check_opts(name: str, opts: dict, allowed: set[str], steps: int) -> list[str]:
    errors = []
    unknown = sorted(set(opts) - allowed)
    if unknown:
        errors.append(f"{name}: unknown options {unknown}; allowed: {sorted(allowed)}")
    for key in ("before", "after"):
        if key in opts and key in allowed:
            value = opts[key]
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= steps:
                errors.append(f"{name}: {key} must be a step number between 1 and {steps}")
    if "path" in opts and "path" in allowed and (not isinstance(opts["path"], str) or not opts["path"]):
        errors.append(f"{name}: path must be a non-empty string")
    if "times" in opts and "times" in allowed and opts["times"] not in TIMES:
        errors.append(f"{name}: times must be one of {list(TIMES)}")
    return errors


def check_block(block, where: str) -> list[str]:
    """Validate one parsed scenario block. `where` prefixes every error."""
    if not isinstance(block, dict):
        return [f"{where}: the block must be a JSON object"]
    errors: list[str] = []

    missing = sorted(REQUIRED - set(block))
    if missing:
        errors.append(f"{where}: missing keys {missing}")
    unknown = sorted(set(block) - REQUIRED - set(OPTIONAL))
    if unknown:
        errors.append(f"{where}: unknown keys {unknown}")

    steps = block.get("steps")
    if "steps" in block and not _is_str_list(steps):
        errors.append(f"{where}: steps must be a non-empty list of strings")
    n_steps = len(steps) if _is_str_list(steps) else 0
    for key in ("expected", "fail_if"):
        if key in block and (not isinstance(block[key], str) or not block[key].strip()):
            errors.append(f"{where}: {key} must be a non-empty string")
    if "setup" in block and not _is_str_list(block["setup"], allow_empty=True):
        errors.append(f"{where}: setup must be a list of strings")
    if "continues" in block and not (isinstance(block["continues"], str)
                                     and re.fullmatch(r"S\d+", block["continues"])):
        errors.append(f"{where}: continues must be 'S<n>'")
    for key, values in FIXED.items():
        if key in block and block[key] not in values:
            errors.append(f"{where}: {key} must be one of {list(values)}")

    checks = block.get("checks")
    if "checks" in block:
        if not isinstance(checks, list) or not checks:
            errors.append(f"{where}: checks must be a non-empty list")
            checks = []
        for position, item in enumerate(checks, start=1):
            label = f"{where}: check {position}"
            if not isinstance(item, list) or not item or not isinstance(item[0], str):
                errors.append(f"{label}: must be a list starting with the check name")
                continue
            name, rest = item[0], item[1:]
            if name not in CHECKS:
                errors.append(f"{label}: unknown check {name!r}; known: {sorted(CHECKS)}")
                continue
            shapes, allowed = CHECKS[name]
            opts = rest.pop() if rest and isinstance(rest[-1], dict) else {}
            if len(rest) != len(shapes):
                errors.append(f"{label}: {name} takes {len(shapes)} argument(s) "
                              f"{list(shapes)}, got {len(rest)}")
                continue
            for shape, value in zip(shapes, rest):
                problem = _check_arg(shape, value)
                if problem:
                    errors.append(f"{label}: {name}: {problem}")
            errors.extend(f"{label}: {e}" for e in _check_opts(name, opts, allowed, n_steps))
    return errors


def _blocks(lines: list[str], start: int, end: int) -> list[tuple[int, str]]:
    """The ```json blocks between two line indexes: (opening line number, text)."""
    found, index = [], start
    while index < end:
        if FENCE_OPEN_RE.match(lines[index]):
            open_no, body = index + 1, []
            index += 1
            while index < end and not FENCE_CLOSE_RE.match(lines[index]):
                body.append(lines[index])
                index += 1
            found.append((open_no, "\n".join(body)))
        index += 1
    return found


def check(lines: list[str]) -> list[str]:
    errors: list[str] = []
    scenarios: list[tuple[int, int, str]] = []  # line number, scenario number, set

    for index, line in enumerate(lines):
        heading = HEADING_RE.match(line)
        if not heading:
            continue
        number = int(heading.group(1))
        follower = lines[index + 1] if index + 1 < len(lines) else ""
        marker = SET_RE.match(follower)
        if not marker:
            errors.append(
                f"line {index + 1}: S{number} is not followed by a `- **Set:**` line"
            )
            scenarios.append((index + 1, number, ""))
            continue
        name = marker.group(1)
        if name not in SETS:
            errors.append(
                f"line {index + 2}: S{number} has set {name!r}, expected one of "
                + " or ".join(SETS)
            )
        scenarios.append((index + 1, number, name))

    if not scenarios:
        return ["no scenario headings found"]

    for position, (line_no, number, _) in enumerate(scenarios, start=1):
        if number != position:
            errors.append(
                f"line {line_no}: S{number} is the {position}. scenario in the file; "
                f"expected S{position}"
            )

    seen_comfort = None
    for line_no, number, name in scenarios:
        if name == "Comfort" and seen_comfort is None:
            seen_comfort = number
        elif name == "Core" and seen_comfort is not None:
            errors.append(
                f"line {line_no}: Core S{number} comes after Comfort S{seen_comfort}; "
                "the Core scenarios come first"
            )
            break  # one report is enough; every later Core repeats it

    known = {number: line_no for line_no, number, _ in scenarios}
    for index, line in enumerate(lines):
        for match in MENTION_RE.finditer(line):
            number = int(match.group(1))
            if number not in known:
                errors.append(f"line {index + 1}: mentions S{number}, which does not exist")
                continue
            if CONTINUE_RE.search(line) and known[number] > index + 1:
                errors.append(
                    f"line {index + 1}: continues S{number}, which comes later in the file"
                )

    # the JSON block of each scenario: its section runs to the next heading
    for position, (line_no, number, _) in enumerate(scenarios):
        start = line_no  # index of the line after the heading
        end = scenarios[position + 1][0] - 1 if position + 1 < len(scenarios) else len(lines)
        for index in range(start, end):
            if SECTION_RE.match(lines[index]):
                end = index
                break
        blocks = _blocks(lines, start, end)
        if not blocks:
            errors.append(f"line {line_no}: S{number} has no ```json block")
            continue
        if len(blocks) > 1:
            errors.append(f"line {blocks[1][0]}: S{number} has more than one ```json block")
            continue
        open_no, text = blocks[0]
        where = f"line {open_no}: S{number}"
        try:
            block = json.loads(text)
        except ValueError as exc:
            errors.append(f"{where}: the block is not valid JSON ({exc})")
            continue
        errors.extend(check_block(block, where))
        target = block.get("continues") if isinstance(block, dict) else None
        if isinstance(target, str) and re.fullmatch(r"S\d+", target):
            other = int(target[1:])  # a missing target is reported by the mention scan
            if other in known and known[other] >= line_no:
                errors.append(f"{where}: continues {target}, which does not come before it")
    return errors


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT
    if not path.is_file():
        print(f"no scenario file at {path}", file=sys.stderr)
        return 1

    errors = check(path.read_text(encoding="utf-8").splitlines())
    rel = path.name if path.is_absolute() else path
    if errors:
        print(f"FAIL {rel}")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(f"ok   {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
