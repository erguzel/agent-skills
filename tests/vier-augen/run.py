#!/usr/bin/env python3
"""vier-augen behaviour scenarios - semi-automated harness.

  python3 tests/vier-augen/run.py --list            scenarios and what they cover
  python3 tests/vier-augen/run.py S05               run one scenario session
  python3 tests/vier-augen/run.py --steps S05       print a scenario's messages again
  python3 tests/vier-augen/run.py --affected        scenarios touched by SKILL.md changes
  python3 tests/vier-augen/run.py --report          latest result per scenario

Options for a run: --isolated (fresh agent config dir), --no-launch (prepare
the fixture and print the messages; start the agent yourself), --profile NAME.
See tests/vier-augen/README.md.
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import datetime as dt
import importlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Dict, List, Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harness as h  # noqa: E402

RESULTS = Path(os.environ.get("VA_RESULTS", HERE / "results"))
STEPS_FILE = Path(tempfile.gettempdir()) / "va-steps.txt"


def load_scenarios() -> Dict[str, h.Scenario]:
    scenarios = {}
    for path in sorted((HERE / "scenarios").glob("S*.py")):
        spec = importlib.util.spec_from_file_location(f"va_{path.stem}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        scenario = module.SCENARIO
        scenarios[scenario.id] = scenario
    return scenarios


def find(scenarios: Dict[str, h.Scenario], wanted: str) -> h.Scenario:
    key = wanted.upper()
    if re.fullmatch(r"S\d", key):
        key = "S0" + key[1]
    if key in scenarios:
        return scenarios[key]
    for scenario in scenarios.values():
        if key in scenario.parts:
            sys.exit(f"{key} runs inside session {scenario.id}: "
                     f"python3 tests/vier-augen/run.py {scenario.id}")
    sys.exit(f"unknown scenario {wanted}; see --list")


def load_profile(name: str):
    return importlib.import_module("profiles." + name.replace("-", "_"))


def skill_version() -> str:
    sha = h.git("log", "-1", "--format=%h", "--", "skills/vier-augen", cwd=h.REPO, check=False)
    dirty = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "skills/vier-augen"],
                           cwd=h.REPO).returncode != 0
    return (sha or "unknown") + ("+dirty" if dirty else "")


def steps_text(scenario: h.Scenario, profile) -> str:
    lines = [f"{scenario.id} - {scenario.title}", ""]
    if scenario.headless:
        lines.append("Runs headless; nothing to type.")
        return "\n".join(lines)
    lines.append(f"  0. {profile.INVOKE}")
    for number, step in enumerate(scenario.steps, 1):
        lines.append(f"  {number}. {step.say}")
        if step.hint:
            lines.append(f"     ({step.hint})")
    lines += ["", "Send each message after the agent has answered the previous one.",
              "Then leave the agent (/exit)."]
    if scenario.notes:
        lines += ["", scenario.notes]
    return "\n".join(lines)


def copy_to_clipboard(text: str) -> bool:
    tool = shutil.which("pbcopy")
    if not tool:
        return False
    subprocess.run([tool], input=text, text=True)
    return True


def ask(question: str) -> h.Result:
    if not sys.stdin.isatty():
        return None
    while True:
        reply = input(f"  {question} [y/n/s=skip] ").strip().lower()
        if reply in ("y", "yes", "j", "e", "evet"):
            return True
        if reply in ("n", "no", "h", "hayir", "hayır"):
            return False
        if reply in ("s", "skip", ""):
            return None


def section_headings() -> set:
    return {line[3:].strip() for line in h.SKILL_MD.read_text(encoding="utf-8").splitlines()
            if line.startswith("## ")}


def cmd_list(scenarios: Dict[str, h.Scenario]) -> None:
    headings = section_headings()
    for scenario in scenarios.values():
        unknown = [c for c in scenario.covers if c != "*" and c not in headings]
        if unknown:
            print(f"warning: {scenario.id} covers unknown SKILL.md sections: {', '.join(unknown)}")
    for scenario in scenarios.values():
        flags = [] if scenario.fresh_fixture else ["continues fixture"]
        if scenario.headless:
            flags.append("headless")
        if scenario.optional:
            flags.append("optional")
        extra = f"  [{', '.join(flags)}]" if flags else ""
        print(f"{scenario.id}  parts {','.join(scenario.parts):<16} "
              f"covers {', '.join(scenario.covers)}{extra}\n     {scenario.title}")


def changed_sections(base: str) -> Optional[set]:
    rel = "skills/vier-augen/SKILL.md"
    diff = subprocess.run(["git", "diff", "-U0", base, "--", rel], cwd=h.REPO,
                          capture_output=True, text=True).stdout
    if not diff.strip():
        return set()
    old = subprocess.run(["git", "show", f"{base}:{rel}"], cwd=h.REPO,
                         capture_output=True, text=True).stdout.splitlines()
    new = h.SKILL_MD.read_text(encoding="utf-8").splitlines()

    def heading_at(lines: List[str], number: int) -> Optional[str]:
        for line in reversed(lines[:max(number, 1)]):
            if line.startswith("## "):
                return line[3:].strip()
        return None                                  # frontmatter or intro

    sections = set()
    for match in re.finditer(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", diff, re.M):
        for lines, start, count in ((old, match.group(1), match.group(2)),
                                    (new, match.group(3), match.group(4))):
            start, count = int(start), int(count or 1)
            for number in range(start, start + max(count, 1)):
                heading = heading_at(lines, number)
                if heading is None:
                    return None                       # intro changed: everything
                sections.add(heading)
    return sections


def cmd_affected(scenarios: Dict[str, h.Scenario], base: str) -> None:
    sections = changed_sections(base)
    if sections == set():
        print(f"SKILL.md has no changes against {base}.")
        return
    label = "frontmatter or intro (all scenarios)" if sections is None else ", ".join(sorted(sections))
    print(f"Changed in SKILL.md against {base}: {label}")
    for scenario in scenarios.values():
        if sections is None or "*" in scenario.covers or sections & set(scenario.covers):
            print(f"  {scenario.id}  ({', '.join(scenario.parts)})")


def cmd_report(scenarios: Dict[str, h.Scenario]) -> None:
    latest: Dict[str, Dict] = {}
    for path in sorted(RESULTS.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for part, result in data["parts"].items():
            latest[part] = {**result, "file": path.name, **{k: data[k] for k in
                            ("skill_version", "date", "agent", "model", "config")}}
    parts = [p for s in scenarios.values() for p in s.parts]
    print("| Part | Status | Skill version | Date | Agent / model | Config |")
    print("| --- | --- | --- | --- | --- | --- |")
    for part in sorted(parts):
        r = latest.get(part)
        if r is None:
            print(f"| {part} | not run | | | | |")
        else:
            print(f"| {part} | {r['status']} | {r['skill_version']} | {r['date'][:16]} | "
                  f"{r['agent']} / {r['model'] or '?'} | {r['config']} |")


def agent_env(isolated: bool) -> Dict[str, str]:
    env = dict(os.environ)
    if isolated:
        env["CLAUDE_CONFIG_DIR"] = str(Path(tempfile.gettempdir()) / "va-agent-config")
        Path(env["CLAUDE_CONFIG_DIR"]).mkdir(exist_ok=True)
    return env


def run(scenario: h.Scenario, scenarios: Dict[str, h.Scenario], profile, args) -> None:
    env = agent_env(args.isolated)
    if args.isolated:
        print("Isolated agent config: the agent may ask you to log in again.")
    errors, warnings, config = profile.preflight(env)
    for warning in warnings:
        print(f"warning: {warning}")
    if errors and not args.force:
        for error in errors:
            print(f"error: {error}")
        sys.exit("Stopped. Fix the above or pass --force (the result is then marked forced).")
    if scenario.requires:
        problem = scenario.requires()
        if problem:
            sys.exit(problem)

    if scenario.fresh_fixture:
        h.build_fixture(profile.SKILL_DIRS)
    if scenario.setup:
        scenario.setup()
    baseline = h.save_baseline()
    session_id = str(uuid.uuid4())
    text = steps_text(scenario, profile)
    STEPS_FILE.write_text(text + "\n", encoding="utf-8")

    print(f"\nFixture ready: {h.FIXTURE}\n")
    print(text)
    print(f"\n(The messages are also in {STEPS_FILE}.)")

    if scenario.headless:
        argv = profile.launch_argv(session_id, headless_prompt=scenario.steps[0].say)
        print(f"\nRunning: {' '.join(argv)}\n")
        subprocess.run(argv, cwd=h.FIXTURE, env=env)
    elif args.no_launch:
        print(f"\nStart the agent yourself, from {h.FIXTURE}, with:\n  "
              f"{' '.join(profile.launch_argv(session_id))}\n"
              f"Then finish with: python3 tests/vier-augen/run.py --finish {scenario.id} {session_id}")
        return
    else:
        if copy_to_clipboard(profile.INVOKE):
            print(f"'{profile.INVOKE}' is on the clipboard.")
        input("\nPress Enter to start the agent... ")
        subprocess.run(profile.launch_argv(session_id), cwd=h.FIXTURE, env=env)

    finish(scenario, profile, session_id, env, config + ("+forced" if errors else ""), baseline)


def finish(scenario: h.Scenario, profile, session_id: str, env: Dict[str, str],
           config: str, baseline: Optional[Dict] = None) -> None:
    if baseline is None:
        baseline = json.loads(h.BASELINE.read_text(encoding="utf-8"))
    transcript = profile.load_transcript(session_id, env)
    positions = None
    loaded: h.Result = None
    if transcript is None:
        print("\nTranscript not found: transcript-based checks are undetermined.")
    elif not transcript.usable:
        print("\nTranscript could not be read: transcript-based checks are undetermined.")
    else:
        loaded = h.skill_loaded(transcript)
        texts = [step.say for step in scenario.steps]
        positions = transcript.step_positions(texts)
        if positions is None:
            print("\nNot every message was found in the transcript: "
                  "checks tied to message order are undetermined.")
    if loaded is None and not scenario.headless:
        loaded = ask("Did the skill load when you invoked it?")
    if loaded is False:
        print("\nThe skill did not load. This run is INVALID - it says nothing about the skill.")

    ctx = h.Context(transcript=transcript, positions=positions, baseline=baseline)
    answers: Dict[str, h.Result] = {}
    if loaded is not False and scenario.questions:
        print("\nYour judgement ('yes' is the expected behaviour):")
        for question in scenario.questions:
            answers[question.text] = ask(f"[{question.part}] {question.text}")
    parts = h.evaluate(scenario, ctx, answers, loaded)

    now = dt.datetime.now(dt.timezone.utc)
    record = {
        "scenario": scenario.id,
        "parts": parts,
        "date": now.isoformat(timespec="seconds"),
        "skill_version": skill_version(),
        "agent": profile.NAME,
        "model": transcript.model if transcript else None,
        "config": config,
        "session_id": session_id,
        "skill_loaded": loaded,
    }
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"{now.strftime('%Y%m%dT%H%M%SZ')}-{scenario.id}-{session_id[:8]}.json"
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\nResult:")
    for part, result in parts.items():
        print(f"  {part}: {result['status'].upper()}")
        for item in result["items"]:
            if item["result"] is not True:
                name = item.get("check") or item.get("question")
                mark = "FAILED" if item["result"] is False else "undetermined"
                print(f"      {mark}: {name}")
    print(f"\nSaved to {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("scenario", nargs="?")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--steps", metavar="ID")
    parser.add_argument("--affected", action="store_true")
    parser.add_argument("--base", default="HEAD", help="git ref for --affected (default HEAD)")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--finish", nargs=2, metavar=("ID", "SESSION_ID"))
    parser.add_argument("--profile", default="claude-code")
    parser.add_argument("--isolated", action="store_true")
    parser.add_argument("--no-launch", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    scenarios = load_scenarios()
    profile = load_profile(args.profile)
    if args.list:
        cmd_list(scenarios)
    elif args.steps:
        print(steps_text(find(scenarios, args.steps), profile))
    elif args.affected:
        cmd_affected(scenarios, args.base)
    elif args.report:
        cmd_report(scenarios)
    elif args.finish:
        env = agent_env(args.isolated)
        _, _, config = profile.preflight(env)
        finish(find(scenarios, args.finish[0]), profile, args.finish[1], env, config)
    elif args.scenario:
        run(find(scenarios, args.scenario), scenarios, profile, args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
