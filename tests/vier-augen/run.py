#!/usr/bin/env python3
"""vier-augen test runner.

  python3 tests/vier-augen/run.py verify        the mechanical layer: hooks and guard
  python3 tests/vier-augen/run.py --list        the scenarios, their sets and chains
  python3 tests/vier-augen/run.py --affected BASE   the scenarios a SKILL.md change affects
  python3 tests/vier-augen/run.py S10 S17       behaviour scenarios (selection only, for now)

`verify` wraps the checks under Verify in the skill's README. It needs no agent
and costs nothing: it builds a throwaway repository, installs the hooks there
and hands each hook - and the adapter's guard - the input it is meant to stop.
The hooks are ON for it.

The scenarios measure the instruction layer instead, with the hooks OFF. The two
never run in one command - each masks the other.

A scenario target resolves the sessions it continues (S4 runs as S3 then S4);
--only skips that. The driver that executes them is not here yet; until it is,
the resolved plan is printed and the scenarios stay a hand-run.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SKILL = ROOT / "skills" / "vier-augen"
SKILL_MD_REL = "skills/vier-augen/SKILL.md"

SCENARIO = re.compile(r"^S\d{1,2}$", re.IGNORECASE)
SETS = {"core", "comfort"}
SCENARIOS_MD = HERE / "scenarios.md"
COVERS_RE = re.compile(r"^- \*\*Covers:\*\* (.+)$")


@dataclass
class Scenario:
    """One scenario: its heading data and the JSON block, as scenarios.md carries them."""

    id: str
    set: str
    title: str
    covers: list[str]
    block: dict

    @property
    def continues(self) -> str | None:
        return self.block.get("continues")


def _validator():
    """The scenario file's grammar lives in tools/validate_scenarios.py; reuse it."""
    sys.path.insert(0, str(ROOT / "tools"))
    import validate_scenarios
    return validate_scenarios


def load_scenarios(path: Path = SCENARIOS_MD) -> dict[str, Scenario]:
    """Parse the scenario file, in file order. The validator's grammar is the gate."""
    vs = _validator()
    lines = path.read_text(encoding="utf-8").splitlines()
    errors = vs.check(lines)
    if errors:
        raise ValueError(f"{path.name} does not validate ({len(errors)} error(s)); "
                         f"run python3 tools/validate_scenarios.py {path}")
    headings = [(i, m) for i, m in ((i, vs.HEADING_RE.match(line))
                                    for i, line in enumerate(lines)) if m]
    scenarios: dict[str, Scenario] = {}
    for index, match in headings:
        end = len(lines)
        for j in range(index + 1, len(lines)):
            if vs.SECTION_RE.match(lines[j]):
                end = j
                break
        name, covers = "", []
        for line in lines[index + 1:end]:
            set_match = vs.SET_RE.match(line)
            if set_match:
                name = set_match.group(1)
            covers_match = COVERS_RE.match(line)
            if covers_match:
                covers = [part.strip() for part in covers_match.group(1).split(",")]
        block = json.loads(vs._blocks(lines, index + 1, end)[0][1])
        sid = f"S{int(match.group(1))}"
        scenarios[sid] = Scenario(sid, name, match.group(2), covers, block)
    return scenarios


def resolve(targets: list[str], scenarios: dict[str, Scenario],
            only: bool = False) -> list[str]:
    """Expand sets, resolve continues-chains unless `only`, and keep file order."""
    wanted: list[str] = []
    for target in targets:
        key = target.lower()
        if key in SETS:
            wanted += [sid for sid, s in scenarios.items() if s.set.lower() == key]
            continue
        if not SCENARIO.match(key):
            raise ValueError(f"unknown target: {target}. Expected verify, a scenario id "
                             f"such as S10, or a set (core, comfort).")
        sid = f"S{int(key[1:])}"
        if sid not in scenarios:
            raise ValueError(f"unknown scenario {target}; see --list")
        wanted.append(sid)
    picked: set[str] = set()
    for sid in wanted:
        picked.add(sid)
        current = scenarios[sid].continues
        while current and not only:
            if current in picked:
                break
            picked.add(current)
            current = scenarios[current].continues
    return [sid for sid in scenarios if sid in picked]


def cmd_list(scenarios: dict[str, Scenario]) -> None:
    for s in scenarios.values():
        flags = []
        if s.continues:
            flags.append(f"continues {s.continues}")
        if s.block.get("fixture") == "keep":
            flags.append("keeps the fixture")
        if s.block.get("mode") == "headless":
            flags.append("headless")
        extra = f"  [{', '.join(flags)}]" if flags else ""
        print(f"{s.id:<4} {s.set:<8} {s.title}{extra}")
        if s.covers:
            print(f"     covers {', '.join(s.covers)}")


def changed_sections(base: str, repo: Path = ROOT) -> set[str] | None:
    """The SKILL.md sections a diff against `base` touches; None means everything.

    A hunk is mapped to the `## ` heading above it, on the old and the new side.
    A hunk above the first heading - frontmatter or intro - affects everything.
    """
    diff = subprocess.run(["git", "diff", "-U0", base, "--", SKILL_MD_REL],
                          cwd=repo, capture_output=True, text=True)
    if diff.returncode != 0:
        raise ValueError(f"git diff against {base!r} failed: {diff.stderr.strip()}")
    if not diff.stdout.strip():
        return set()
    old = subprocess.run(["git", "show", f"{base}:{SKILL_MD_REL}"], cwd=repo,
                         capture_output=True, text=True).stdout.splitlines()
    new = (repo / SKILL_MD_REL).read_text(encoding="utf-8").splitlines()

    def heading_at(lines: list[str], number: int) -> str | None:
        for line in reversed(lines[:max(number, 1)]):
            if line.startswith("## "):
                return line[3:].strip()
        return None

    sections: set[str] = set()
    for match in re.finditer(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@",
                             diff.stdout, re.M):
        for lines, start, count in ((old, match.group(1), match.group(2)),
                                    (new, match.group(3), match.group(4))):
            start, count = int(start), int(count or 1)
            for number in range(start, start + max(count, 1)):
                heading = heading_at(lines, number)
                if heading is None:
                    return None
                sections.add(heading)
    return sections


def cmd_affected(base: str, scenarios: dict[str, Scenario],
                 repo: Path = ROOT) -> list[str]:
    """The scenarios whose Covers meet the sections changed against `base`."""
    headings = {line[3:].strip() for line in
                (repo / SKILL_MD_REL).read_text(encoding="utf-8").splitlines()
                if line.startswith("## ")}
    for s in scenarios.values():
        unknown = [c for c in s.covers if c not in headings]
        if unknown:
            print(f"warning: {s.id} covers unknown SKILL.md sections: "
                  f"{', '.join(unknown)}")
    sections = changed_sections(base, repo)
    if sections == set():
        print(f"SKILL.md has no changes against {base}.")
        return []
    label = ("frontmatter or intro (every scenario)" if sections is None
             else ", ".join(sorted(sections)))
    print(f"Changed against {base}: {label}")
    return [sid for sid, s in scenarios.items()
            if sections is None or sections & set(s.covers)]


class Report:
    """What ran, what held, and one line of detail when it did not."""

    def __init__(self) -> None:
        self.items: list[tuple[str, bool, str]] = []

    def add(self, name: str, ok: bool, detail: str = "") -> bool:
        self.items.append((name, ok, detail))
        print(f"  {'ok  ' if ok else 'FAIL'} {name}")
        if not ok and detail:
            print(f"         {detail}")
        return ok

    def failed(self) -> list[str]:
        return [name for name, ok, _ in self.items if not ok]


def git_env() -> dict:
    """A git environment the operator's own configuration cannot colour."""
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    env["GIT_TERMINAL_PROMPT"] = "0"
    for name in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
                 "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
        env.pop(name, None)
    return env


def run(args: list[str], cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, env=env or git_env(),
                          capture_output=True, text=True)


def output(proc: subprocess.CompletedProcess) -> str:
    return proc.stdout + proc.stderr


def refused(proc: subprocess.CompletedProcess, message: str) -> tuple[bool, str]:
    """A hook did its job: non-zero exit and the message it promises."""
    if proc.returncode == 0:
        return False, "the command succeeded; the hook did not run or did not match."
    if message not in output(proc):
        return False, f"refused, but without {message!r}: {output(proc).strip().splitlines()[:1]}"
    return True, ""


def build_repo(root: Path) -> tuple[Path, Path, subprocess.CompletedProcess]:
    """A throwaway repository with the hooks installed, and a bare remote."""
    repo, remote = root / "repo", root / "remote.git"
    run(["git", "init", "-q", str(repo)], cwd=root)
    run(["git", "init", "-q", "--bare", str(remote)], cwd=root)
    run(["git", "config", "user.name", "Test Operator"], cwd=repo)
    run(["git", "config", "user.email", "operator@example.com"], cwd=repo)
    install = run(["sh", str(SKILL / "hooks" / "install.sh")], cwd=repo)
    (repo / "a.txt").write_text("seed\n", encoding="utf-8")
    run(["git", "add", "a.txt"], cwd=repo)
    run(["git", "commit", "-qm", "init: seed"], cwd=repo)
    return repo, remote, install


def verify_hooks(repo: Path, remote: Path, install: subprocess.CompletedProcess,
                 report: Report) -> None:
    print("\nLevel 1 - git hooks")

    hooks = [repo / ".git" / "hooks" / name
             for name in ("commit-msg", "pre-commit", "pre-push")]
    missing = [h.name for h in hooks if not h.is_file()]
    report.add("the three hooks are installed", not missing,
               f"missing: {', '.join(missing)}; installer said: "
               f"{output(install).strip()}" if missing else "")

    (repo / "a.txt").write_text("seed\nmore\n", encoding="utf-8")
    run(["git", "add", "a.txt"], cwd=repo)
    proc = run(["git", "commit", "-m", "test: trailer",
                "-m", "Co-Authored-By: Claude <noreply@anthropic.com>"], cwd=repo)
    report.add("attribution in the message is refused",
               *refused(proc, "assistant attribution found in the message"))

    env = git_env()
    env["GIT_AUTHOR_NAME"] = "Claude"
    env["GIT_AUTHOR_EMAIL"] = "noreply@anthropic.com"
    proc = run(["git", "commit", "-m", "test: identity"], cwd=repo, env=env)
    report.add("an agent identity as author is refused",
               *refused(proc, "coding-agent identity in GIT_AUTHOR_IDENT"))

    # The bait is assembled here so that this file does not trip the hook it tests.
    run(["git", "reset", "-q"], cwd=repo)
    (repo / "secret.txt").write_text("key = " + "AKIA" + "ABCDEFGHIJKLMNOP" + "\n",
                                     encoding="utf-8")
    run(["git", "add", "secret.txt"], cwd=repo)
    proc = run(["git", "commit", "-m", "test: secret"], cwd=repo)
    ok, detail = refused(proc, "possible AWS access key at secret.txt:1")
    report.add("a staged secret is refused", ok, detail)
    report.add("the secret value is not printed",
               "AKIA" + "ABCDEFGHIJKLMNOP" not in output(proc),
               "the hook printed the value it found - a bug worth reporting.")

    run(["git", "reset", "-q"], cwd=repo)
    (repo / "secret.txt").unlink()
    (repo / "pathy.txt").write_text("path = /" + "Users" + "/someone/Projects/thing\n",
                                    encoding="utf-8")
    run(["git", "add", "pathy.txt"], cwd=repo)
    proc = run(["git", "commit", "-m", "test: path"], cwd=repo)
    report.add("a personal home path is refused",
               *refused(proc, "possible personal home path at pathy.txt:1"))

    run(["git", "reset", "-q"], cwd=repo)
    (repo / "pathy.txt").unlink()
    branch = run(["git", "branch", "--show-current"], cwd=repo).stdout.strip()
    run(["git", "remote", "add", "origin", str(remote)], cwd=repo)
    proc = run(["git", "push", "-q", "origin", branch], cwd=repo)
    report.add("an ordinary push passes", proc.returncode == 0,
               f"the push was refused: {output(proc).strip()}")
    run(["git", "commit", "--amend", "--no-verify", "-qm", "init: seed (amended)"], cwd=repo)
    proc = run(["git", "push", "--force", "origin", branch], cwd=repo)
    report.add("a force-push is refused",
               *refused(proc, "would rewrite history on"))


GUARD = SKILL / "adapters" / "claude-code" / "guard.py"


def probe(command: str, cwd: Path) -> subprocess.CompletedProcess:
    """Hand the guard one Bash tool call on stdin, the way the runtime does."""
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    return subprocess.run([sys.executable, str(GUARD)], input=payload, cwd=cwd,
                          capture_output=True, text=True)


def verify_guard(cwd: Path, report: Report) -> None:
    print("\nLevel 2 - agent adapter (Claude Code)")

    answers = []

    proc = probe("git push --force origin main", cwd)
    answers.append(output(proc))
    report.add("the guard blocks a force-push",
               proc.returncode == 2 and "blocked - force-push" in output(proc),
               f"exit={proc.returncode}, said: {output(proc).strip()!r}")

    proc = probe("git status", cwd)
    answers.append(output(proc))
    report.add("the guard leaves a read-only command alone",
               proc.returncode == 0 and not output(proc).strip(),
               f"exit={proc.returncode}, said: {output(proc).strip()!r}")

    proc = probe("git -C . add probe.txt", cwd)
    answers.append(output(proc))
    decision = ""
    try:
        decision = json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"]
    except (ValueError, KeyError, TypeError):
        pass
    report.add("the guard asks for `git -C . add`, which the rules alone would miss",
               proc.returncode == 0 and decision == "ask",
               f"exit={proc.returncode}, said: {output(proc).strip()!r}")

    report.add("the guard decides per command rather than answering alike",
               len(set(answers)) == 3,
               "two of the three probes came back with the same answer - check that "
               "python3 is there and that the guard's path resolves.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("targets", nargs="*",
                        help="verify, or scenario ids (S10) and sets (core, comfort)")
    parser.add_argument("--list", action="store_true",
                        help="list the scenarios, their sets and chains")
    parser.add_argument("--affected", metavar="BASE",
                        help="select the scenarios covering SKILL.md sections "
                             "changed against BASE")
    parser.add_argument("--only", action="store_true",
                        help="run only the named scenarios, not the sessions they continue")
    parser.add_argument("--keep", action="store_true",
                        help="leave the throwaway repository behind for a look")
    args = parser.parse_args()

    if args.list:
        try:
            cmd_list(load_scenarios())
        except ValueError as exc:
            sys.exit(str(exc))
        return
    if args.affected:
        if args.targets:
            sys.exit("--affected selects its own scenarios; do not also name targets.")
        try:
            scenarios = load_scenarios()
            affected = cmd_affected(args.affected, scenarios)
        except ValueError as exc:
            sys.exit(str(exc))
        if not affected:
            return
        print("Affected: " + " ".join(affected))
        print("Run order: " + " ".join(resolve(affected, scenarios, only=args.only)))
        sys.exit("The scenarios are not runnable from here yet: the driver is not here. "
                 "Until it is, tests/vier-augen/scenarios.md carries them for a hand-run.")
    targets = [t.lower() for t in args.targets]
    if not targets:
        parser.print_help()
        return
    wants_verify = "verify" in targets
    rest = [t for t in targets if t != "verify"]
    if wants_verify and rest:
        sys.exit("verify and the scenarios do not run in one command: verify measures "
                 "with the hooks on, the scenarios with them off. Each masks the other.")
    if rest:
        try:
            plan = resolve(rest, load_scenarios(), only=args.only)
        except ValueError as exc:
            sys.exit(str(exc))
        print("Run order: " + " ".join(plan))
        sys.exit("The scenarios are not runnable from here yet: the driver is not here. "
                 "Until it is, tests/vier-augen/scenarios.md carries them for a hand-run.")

    root = Path(tempfile.mkdtemp(prefix="va-verify-"))
    report = Report()
    try:
        repo, remote, install = build_repo(root)
        verify_hooks(repo, remote, install, report)
        verify_guard(repo, report)
    finally:
        if args.keep:
            print(f"\nLeft behind: {root}")
        else:
            shutil.rmtree(root, ignore_errors=True)

    failed = report.failed()
    print(f"\n{len(report.items) - len(failed)}/{len(report.items)} checks held.")
    if failed:
        print("Failed: " + ", ".join(failed))
        sys.exit(1)


if __name__ == "__main__":
    main()
