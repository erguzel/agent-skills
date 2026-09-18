#!/usr/bin/env python3
"""Validate the structure of a behaviour scenario file.

  - every scenario heading is followed by a `- **Set:** Core|Comfort` line
  - scenarios are numbered from 1 upwards, without gaps or repeats
  - the Core scenarios come before the Comfort ones
  - every `S<n>` the file mentions is a scenario that exists, and a scenario
    that continues another comes after it

It checks the shape of the file, not what the scenarios say. Takes the file as
its one argument; defaults to tests/vier-augen/scenarios.md.

Exit code 1 on any failure. No third-party dependencies.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DEFAULT = Path(__file__).resolve().parent.parent / "tests" / "vier-augen" / "scenarios.md"

HEADING_RE = re.compile(r"^### S(\d+) - (.+)$")
SET_RE = re.compile(r"^- \*\*Set:\*\* (\S+)\s*$")
MENTION_RE = re.compile(r"\bS(\d+)\b")
CONTINUE_RE = re.compile(r"\*\*Continue (?:from )?S(\d+)")
SETS = ("Core", "Comfort")


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
