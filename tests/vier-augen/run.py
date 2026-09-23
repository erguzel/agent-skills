#!/usr/bin/env python3
"""vier-augen test runner.

  python3 tests/vier-augen/run.py verify        the mechanical layer: hooks and guard
  python3 tests/vier-augen/run.py --list        the scenarios, their sets and chains
  python3 tests/vier-augen/run.py --affected BASE   the scenarios a SKILL.md change affects
  python3 tests/vier-augen/run.py S7            run a scenario and the session it continues
  python3 tests/vier-augen/run.py --report      the latest result per scenario

`verify` wraps the checks under Verify in the skill's README. It needs no agent
and costs nothing: it builds a throwaway repository, installs the hooks there
and hands each hook - and the adapter's guard - the input it is meant to stop.
The hooks are ON for it.

The scenarios measure the instruction layer instead, with the hooks OFF. The two
never run in one command - each masks the other.

A scenario target resolves the sessions it continues (S4 runs as S3 then S4);
--only skips that. The default driver is headless, driving the agent through
profiles/; --driver manual prepares the fixture and hands the session to you.
Run results are kept outside the repository (VA_RESULTS, default /tmp/va-results).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import importlib
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SKILL = ROOT / "skills" / "vier-augen"
SKILL_MD_REL = "skills/vier-augen/SKILL.md"

SCENARIO = re.compile(r"^S\d{1,2}$", re.IGNORECASE)
SETS = {"core", "comfort"}
SCENARIOS_MD = HERE / "scenarios.md"
COVERS_RE = re.compile(r"^- \*\*Covers:\*\* (.+)$")
# /tmp, not the platform temp dir: build-fixture.sh and the documents say
# /tmp/va-fixture, and on macOS gettempdir() is a per-user folder instead.
FIXTURE = Path(os.environ.get("VA_FIXTURE", "/tmp/va-fixture"))
REMOTE = FIXTURE.parent / (FIXTURE.name + "-remote.git")
RESULTS = Path(os.environ.get("VA_RESULTS", "/tmp/va-results"))
BUILD_FIXTURE = HERE / "build-fixture.sh"


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
    """Expand sets, resolve continues-chains unless `only`, and keep file order -
    except that a scenario continuing a picked one goes directly after it, so a
    chain stays one conversation whatever sits between its members in the file."""
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
    ordered: list[str] = []
    for sid in scenarios:
        if sid not in picked:
            continue
        cont = scenarios[sid].continues
        if cont and cont in ordered:
            ordered.insert(ordered.index(cont) + 1, sid)
        else:
            ordered.append(sid)
    return ordered


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


def probe(command: str, cwd: Path, guard: Path = GUARD) -> subprocess.CompletedProcess:
    """Hand the guard one Bash tool call on stdin, the way the runtime does."""
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    return subprocess.run([sys.executable, str(guard)], input=payload, cwd=cwd,
                          capture_output=True, text=True)


def decision_of(proc: subprocess.CompletedProcess) -> str:
    try:
        return json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"]
    except (ValueError, KeyError, TypeError):
        return ""


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
    report.add("the guard asks for `git -C . add`, which the rules alone would miss",
               proc.returncode == 0 and decision_of(proc) == "ask",
               f"exit={proc.returncode}, said: {output(proc).strip()!r}")

    report.add("the guard decides per command rather than answering alike",
               len(set(answers)) == 3,
               "two of the three probes came back with the same answer - check that "
               "python3 is there and that the guard's path resolves.")

    proc = probe("while read l; do git push --force origin main; done < refs.txt", cwd)
    report.add("the guard blocks a force-push inside a loop",
               proc.returncode == 2 and "blocked - force-push" in output(proc),
               f"exit={proc.returncode}, said: {output(proc).strip()!r}")

    proc = probe('for f in a b; do rm "$f"; done', cwd)
    report.add("the guard asks for a deletion inside a loop",
               proc.returncode == 0 and decision_of(proc) == "ask",
               f"exit={proc.returncode}, said: {output(proc).strip()!r}")

    proc = probe('bash -c "git push --force origin main"', cwd)
    report.add("the guard blocks a force-push handed to a shell as a string",
               proc.returncode == 2 and "blocked - force-push" in output(proc),
               f"exit={proc.returncode}, said: {output(proc).strip()!r}")

    # The guard copied out alone, without the skill's classifier beside it: it
    # must ask for everything and say why, never fall open.
    alone = cwd / "guard-alone"
    alone.mkdir()
    shutil.copy(GUARD, alone / "guard.py")
    proc = probe("git status", cwd, guard=alone / "guard.py")
    report.add("the guard asks for everything when the classifier is missing, rather than fall open",
               proc.returncode == 0 and decision_of(proc) == "ask"
               and "classifier" in proc.stderr,
               f"exit={proc.returncode}, said: {output(proc).strip()!r}")


# --------------------------------------------------------------------------
# The driver: prepare a fixture, run the agent, judge the transcript.

def _harness():
    sys.path.insert(0, str(HERE))
    import harness
    return harness


def load_profile(name: str):
    sys.path.insert(0, str(HERE))
    return importlib.import_module("profiles." + name.replace("-", "_"))


@dataclass
class Run:
    """One agent conversation: the scenarios it covers, on one fixture state."""

    scenarios: list[str]
    rebuild: bool


def plan_runs(plan: list[str], scenarios: dict[str, Scenario]) -> list[Run]:
    """Group the run order into conversations. A continues-chain shares one; a
    fixture:keep scenario is a new conversation on the same fixture; the rest
    each rebuild the fixture."""
    runs: list[Run] = []
    for sid in plan:
        block = scenarios[sid].block
        cont = block.get("continues")
        if cont and runs and cont in runs[-1].scenarios:
            runs[-1].scenarios.append(sid)
        elif cont and cont in plan:
            raise ValueError(f"{sid} continues {cont}, but {cont} does not come directly "
                             f"before it; the chain would run as two sessions.")
        elif block.get("fixture") == "keep" and runs:
            runs.append(Run([sid], rebuild=False))
        else:
            runs.append(Run([sid], rebuild=True))
    return runs


def prepare(run: Run, scenarios: dict[str, Scenario], h, profile) -> dict:
    """Build or keep the fixture, apply each scenario's setup, take the baseline."""
    if run.rebuild or not FIXTURE.exists():
        result = subprocess.run(["sh", str(BUILD_FIXTURE), str(FIXTURE)],
                                capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"build-fixture.sh failed: {result.stderr.strip()}")
    for sid in run.scenarios:
        for command in scenarios[sid].block.get("setup", []):
            done = subprocess.run(command, shell=True, cwd=FIXTURE,
                                  capture_output=True, text=True)
            if done.returncode != 0:
                raise RuntimeError(f"{sid} setup failed ({command!r}): {done.stderr.strip()}")
    baseline = h.save_baseline(FIXTURE, REMOTE, profile)
    baseline["run"] = run.scenarios
    (FIXTURE / ".git" / "va-baseline.json").write_text(
        json.dumps(baseline), encoding="utf-8")
    return baseline


def prompts_for(run: Run, scenarios: dict[str, Scenario], invoke: str):
    """(prompts, headless_single). A mode:headless scenario invokes in one turn."""
    steps: list[str] = []
    for sid in run.scenarios:
        steps += scenarios[sid].block["steps"]
    only = run.scenarios[0]
    if len(run.scenarios) == 1 and scenarios[only].block.get("mode") == "headless":
        return [f"{invoke}\n\n{steps[0]}"], True
    return [invoke] + steps, False


def judge_one(sid, scenarios, profile, env, session_id, baseline, h,
              steps_before: list[str]) -> dict:
    """Judge one scenario against the session as it stands right now.

    Called between scenarios, so the transcript holds nothing from the ones
    that follow and the fixture is in the state this scenario left it.
    """
    block = scenarios[sid].block
    transcript = profile.load_transcript(session_id, env)
    loaded: object = None
    positions = None
    if transcript is None or not transcript.usable:
        print(f"  {sid}: transcript not readable; those checks are undetermined.")
    else:
        loaded = h.skill_loaded(transcript)
        found = transcript.step_positions(steps_before + block["steps"])
        if found is None:
            print(f"  {sid}: not every message was found; order-based checks "
                  "are undetermined.")
        else:
            positions = found[len(steps_before):]
        if loaded is False:
            print(f"  {sid}: the skill text did not reach the session - INVALID.")
    ctx = h.Context(fixture=FIXTURE, remote=REMOTE, profile=profile,
                    baseline=baseline, transcript=transcript, positions=positions)
    return h.run_checks(block, ctx, loaded)


def drive_headless(run, scenarios, profile, env, baseline, h) -> tuple[str, dict]:
    """Drive the session scenario by scenario, judging each as it finishes."""
    session_id = str(uuid.uuid4())
    report: dict = {}
    steps_before: list[str] = []
    turn = 0
    for position, sid in enumerate(run.scenarios):
        block = scenarios[sid].block
        prompts = list(block["steps"])
        if position == 0:
            if len(run.scenarios) == 1 and block.get("mode") == "headless":
                prompts = [f"{profile.INVOKE}\n\n{prompts[0]}"]
            else:
                prompts = [profile.INVOKE] + prompts
        for prompt in prompts:
            argv = profile.launch_argv(session_id, prompt, resume=turn > 0)
            subprocess.run(argv, cwd=FIXTURE, env=env)
            turn += 1
        report[sid] = judge_one(sid, scenarios, profile, env, session_id,
                                baseline, h, steps_before)
        steps_before += block["steps"]
    return session_id, report


def evaluate(run, scenarios, profile, env, session_id, baseline, h) -> dict:
    """Judge a finished session in one go - the manual path.

    Every scenario's checks are bounded above by the next scenario's first
    message, so a later turn cannot be read as this one's. The fixture,
    however, is only seen as the whole session left it: a state check in a
    chained scenario is therefore weaker here than under the driver.
    """
    transcript = profile.load_transcript(session_id, env)
    loaded: object = None
    all_steps: list[str] = []
    for sid in run.scenarios:
        all_steps += scenarios[sid].block["steps"]
    positions = None
    if transcript is None or not transcript.usable:
        print("  transcript not readable: transcript-based checks are undetermined.")
    else:
        loaded = h.skill_loaded(transcript)
        positions = transcript.step_positions(all_steps)
        if positions is None:
            print("  not every message was found: order-based checks are undetermined.")
        if loaded is False:
            print("  the skill text did not reach the session: this run is INVALID.")
    report, offset = {}, 0
    for sid in run.scenarios:
        block = scenarios[sid].block
        count = len(block["steps"])
        local = limit = None
        if positions is not None:
            local = positions[offset:offset + count]
            if offset + count < len(positions):
                limit = positions[offset + count]
        offset += count
        ctx = h.Context(fixture=FIXTURE, remote=REMOTE, profile=profile,
                        baseline=baseline, transcript=transcript, positions=local,
                        limit=limit)
        report[sid] = h.run_checks(block, ctx, loaded)
    return report


def session_model(profile, session_id: str, env: dict) -> str | None:
    """The model the session's transcript names; None when it cannot be read."""
    transcript = profile.load_transcript(session_id, env)
    return transcript.model if transcript is not None else None


def save_results(report: dict, profile, session_id: str, model: str | None) -> Path:
    """Write one run's record. The model is kept even when unknown - as null,
    so a record that cannot say what it measured shows that it cannot."""
    RESULTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    record = {"date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "agent": profile.NAME, "model": model, "session_id": session_id,
              "parts": report}
    out = RESULTS / f"{stamp}-{'-'.join(report)}-{session_id[:8]}.json"
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def show_report(report: dict) -> bool:
    ok = True
    for sid, result in report.items():
        print(f"  {sid}: {result['status'].upper()}")
        for item in result["items"]:
            if item["result"] is not True:
                mark = "failed" if item["result"] is False else "undetermined"
                print(f"      {mark}: {item['check']}")
                if item.get("detail"):
                    print(f"         {item['detail']}")
        if result["status"] in ("fail", "invalid"):
            ok = False
    return ok


def steps_text(run, scenarios, invoke) -> str:
    prompts, _ = prompts_for(run, scenarios, invoke)
    lines = [f"Session {' -> '.join(run.scenarios)}:", ""]
    for number, prompt in enumerate(prompts):
        lines.append(f"  {number}. {prompt}")
    lines += ["", "Send each after the agent has answered the previous one, then /exit."]
    return "\n".join(lines)


def agent_env(isolated: bool) -> dict:
    env = dict(os.environ)
    if isolated:
        env["CLAUDE_CONFIG_DIR"] = str(Path(tempfile.gettempdir()) / "va-agent-config")
        Path(env["CLAUDE_CONFIG_DIR"]).mkdir(exist_ok=True)
    return env


def cmd_report(scenarios: dict[str, Scenario]) -> None:
    latest: dict[str, dict] = {}
    if RESULTS.is_dir():
        for path in sorted(RESULTS.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            for sid, result in data.get("parts", {}).items():
                latest[sid] = {"status": result["status"], "date": data["date"][:16],
                               "agent": data["agent"],
                               "model": data.get("model") or "unknown"}
    print("| Scenario | Status | Date | Agent | Model |")
    print("| --- | --- | --- | --- | --- |")
    for sid in scenarios:
        row = latest.get(sid)
        if row:
            print(f"| {sid} | {row['status']} | {row['date']} | {row['agent']} "
                  f"| {row['model']} |")
        else:
            print(f"| {sid} | not run | | | |")


def drive(rest: list[str], args) -> None:
    h = _harness()
    try:
        scenarios = load_scenarios()
        plan = resolve(rest, scenarios, only=args.only)
        runs = plan_runs(plan, scenarios)
    except ValueError as exc:
        sys.exit(str(exc))
    profile = load_profile(args.profile)
    env = agent_env(args.isolated)
    _, warnings, config = profile.preflight(env)
    for warning in warnings:
        print(f"warning: {warning}")

    overall = True
    for run in runs:
        label = " -> ".join(run.scenarios)
        print(f"\n=== {label} ===")
        try:
            baseline = prepare(run, scenarios, h, profile)
        except RuntimeError as exc:
            sys.exit(str(exc))
        if args.driver == "manual":
            print(f"Fixture ready: {FIXTURE}\n")
            print(steps_text(run, scenarios, profile.INVOKE))
            print(f"\nStart from {FIXTURE} with the {profile.NAME} agent, then:")
            print(f"  python3 tests/vier-augen/run.py --finish {run.scenarios[-1]} <session-id>")
            continue
        session_id, report = drive_headless(run, scenarios, profile, env, baseline, h)
        out = save_results(report, profile, session_id,
                           session_model(profile, session_id, env))
        overall = show_report(report) and overall
        print(f"  saved: {out}")
    if args.driver == "manual":
        return
    if not overall:
        sys.exit(1)


def finish(scenario_id: str, session_id: str, args) -> None:
    h = _harness()
    scenarios = load_scenarios()
    profile = load_profile(args.profile)
    env = agent_env(args.isolated)
    baseline_path = FIXTURE / ".git" / "va-baseline.json"
    if not baseline_path.is_file():
        sys.exit(f"no baseline at {baseline_path}; run --driver manual first.")
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    run = Run(baseline.get("run", [scenario_id]), rebuild=False)
    report = evaluate(run, scenarios, profile, env, session_id, baseline, h)
    save_results(report, profile, session_id, session_model(profile, session_id, env))
    if not show_report(report):
        sys.exit(1)


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
    parser.add_argument("--report", action="store_true",
                        help="show the latest recorded result per scenario")
    parser.add_argument("--driver", choices=("headless", "manual"), default="headless",
                        help="headless drives the agent; manual hands you the session")
    parser.add_argument("--finish", nargs=2, metavar=("ID", "SESSION"),
                        help="judge a manual run from its transcript; the session it\n                              prepared is read from the fixture's baseline")
    parser.add_argument("--profile", default="claude-code",
                        help="the agent profile under profiles/ (default claude-code)")
    parser.add_argument("--isolated", action="store_true",
                        help="give the agent a throwaway config dir")
    parser.add_argument("--keep", action="store_true",
                        help="leave the throwaway repository behind for a look")
    args = parser.parse_args()

    if args.report:
        try:
            cmd_report(load_scenarios())
        except ValueError as exc:
            sys.exit(str(exc))
        return
    if args.finish:
        finish(args.finish[0], args.finish[1], args)
        return

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
        print("Run them: python3 tests/vier-augen/run.py " + " ".join(affected))
        return
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
        drive(rest, args)
        return

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
