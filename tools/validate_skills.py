#!/usr/bin/env python3
"""Validate every skill under skills/ against the Agent Skills spec constraints.

Per skill directory:
  - the directory holds a SKILL.md
  - YAML frontmatter is present and parses
  - required fields: name, description
  - name matches its parent directory exactly
  - name is lowercase letters/digits/hyphens, <= 64 chars, no leading, trailing
    or consecutive hyphens
  - description <= 1024 chars and non-trivial
  - no angle brackets anywhere in frontmatter (they can inject into the prompt)
  - the body stays under the recommended 500-line budget
  - every relative link in SKILL.md resolves to a file that exists

Exit code 1 on any failure. No third-party dependencies.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "#")
MAX_BODY_LINES = 500


def parse_frontmatter(text: str) -> dict[str, str] | None:
    """Minimal top-level `key: value` parser. Enough for skill frontmatter."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None
    fields: dict[str, str] = {}
    key = None
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        if line[0] in " \t" and key:  # folded continuation line
            fields[key] += " " + line.strip()
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        fields[key] = value.strip()
    return fields


def check_frontmatter(text: str, skill_md: Path) -> list[str]:
    errors: list[str] = []

    fields = parse_frontmatter(text)
    if fields is None:
        return ["missing or malformed YAML frontmatter"]

    raw = FRONTMATTER_RE.match(text).group(1)
    if "<" in raw or ">" in raw:
        errors.append("frontmatter contains angle brackets")

    name = fields.get("name")
    if not name:
        errors.append("missing required field: name")
    else:
        if not NAME_RE.match(name):
            errors.append(f"name {name!r} must be lowercase alphanumeric with single hyphens")
        if len(name) > 64:
            errors.append(f"name is {len(name)} chars, max 64")
        if name != skill_md.parent.name:
            errors.append(f"name {name!r} does not match directory {skill_md.parent.name!r}")

    description = fields.get("description")
    if not description:
        errors.append("missing required field: description")
    else:
        if len(description) > 1024:
            errors.append(f"description is {len(description)} chars, max 1024")
        if len(description) < 40:
            errors.append("description is too short to trigger reliably")

    return errors


def check_body(text: str, skill_md: Path) -> list[str]:
    """Budget and link checks on the part an agent loads or follows."""
    errors: list[str] = []

    lines = len(text.splitlines())
    if lines > MAX_BODY_LINES:
        errors.append(f"SKILL.md is {lines} lines, over the {MAX_BODY_LINES}-line budget")

    for target in LINK_RE.findall(text):
        target = target.split()[0].strip("<>")
        if target.startswith(EXTERNAL_PREFIXES):
            continue
        path = target.split("#", 1)[0]
        if not path:
            continue
        if path.startswith("/"):
            errors.append(f"link {target!r} is an absolute path; use a path relative to SKILL.md")
            continue
        if not (skill_md.parent / path).exists():
            errors.append(f"link {target!r} does not resolve to a file")

    return errors


def validate(skill_dir: Path) -> list[str]:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return ["no SKILL.md in this skill directory"]

    text = skill_md.read_text(encoding="utf-8")
    return check_frontmatter(text, skill_md) + check_body(text, skill_md)


def main() -> int:
    skill_dirs = sorted(
        d for d in SKILLS_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")
    ) if SKILLS_DIR.is_dir() else []

    if not skill_dirs:
        print(f"no skill directories found under {SKILLS_DIR}", file=sys.stderr)
        return 1

    failed = False
    for skill_dir in skill_dirs:
        rel = skill_dir.relative_to(SKILLS_DIR.parent)
        errors = validate(skill_dir)
        if errors:
            failed = True
            print(f"FAIL {rel}")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"ok   {rel}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
