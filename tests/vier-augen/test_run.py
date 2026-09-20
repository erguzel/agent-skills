#!/usr/bin/env python3
"""Tests for the scenario selection in run.py: loading scenarios.md, expanding
sets, resolving continues-chains, and the verify/scenario masking rule.

A sabotaged copy of the scenario file must be rejected, never half-loaded.
Exit code 1 on any failure. No third-party dependencies.
"""

from __future__ import annotations

import contextlib
import json
import io
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run as r  # noqa: E402

failures: list[str] = []
total = 0


def case(name: str, ok: bool, detail: str = "") -> None:
    global total
    total += 1
    print(f"{'ok  ' if ok else 'FAIL'} {name}")
    if not ok:
        failures.append(name)
        if detail:
            print(f"       {detail}")


def rejects(name: str, fn) -> None:
    try:
        fn()
    except ValueError:
        case(name, True)
        return
    case(name, False, "no error was raised")


scenarios = r.load_scenarios()
case("the real file loads 21 scenarios", len(scenarios) == 21, str(len(scenarios)))
case("ids run S1..S21 in file order",
     list(scenarios) == [f"S{i}" for i in range(1, 22)])
core = [s for s in scenarios.values() if s.set == "Core"]
comfort = [s for s in scenarios.values() if s.set == "Comfort"]
case("17 Core and 4 Comfort", (len(core), len(comfort)) == (17, 4))
case("S4 continues S3", scenarios["S4"].continues == "S3")
case("S1 covers two sections",
     scenarios["S1"].covers == ["Operator instructions", "Reading files"])
case("S20 keeps the fixture", scenarios["S20"].block.get("fixture") == "keep")
case("S21 is headless", scenarios["S21"].block.get("mode") == "headless")

case("a target resolves the session it continues",
     r.resolve(["S4"], scenarios) == ["S3", "S4"])
case("a chain resolves to its root",
     r.resolve(["S7"], scenarios) == ["S3", "S4", "S6", "S7"])
case("--only skips the chain", r.resolve(["S7"], scenarios, only=True) == ["S7"])
case("a set expands in file order",
     r.resolve(["comfort"], scenarios) == ["S18", "S19", "S20", "S21"])
case("overlapping targets are run once",
     r.resolve(["S7", "S4"], scenarios) == ["S3", "S4", "S6", "S7"])
case("lower case and left-padded ids match",
     r.resolve(["s10"], scenarios) == ["S10"]
     and r.resolve(["S05"], scenarios) == ["S5"])
rejects("an unknown scenario is rejected", lambda: r.resolve(["S99"], scenarios))
rejects("an unknown target is rejected", lambda: r.resolve(["everything"], scenarios))

# Negative controls: a sabotaged copy must be rejected, never half-loaded.
real = r.SCENARIOS_MD.read_text(encoding="utf-8")
tmp = Path(tempfile.gettempdir()) / "va-test-scenarios.md"
tmp.write_text(real.replace('"continues": "S3"', '"continues": "S5"', 1),
               encoding="utf-8")
rejects("a chain pointing forward is rejected", lambda: r.load_scenarios(tmp))
tmp.write_text(real.replace('"steps"', '"steps!!"', 1), encoding="utf-8")
rejects("a block missing a required key is rejected", lambda: r.load_scenarios(tmp))
tmp.unlink()

run_py = str(HERE / "run.py")
proc = subprocess.run([sys.executable, run_py, "verify", "S10"],
                      capture_output=True, text=True)
case("verify and a scenario are refused in one command",
     proc.returncode != 0 and "masks the other" in proc.stderr,
     f"exit={proc.returncode}")
proc = subprocess.run([sys.executable, run_py, "--list"],
                      capture_output=True, text=True)
case("--list exits cleanly and shows every scenario",
     proc.returncode == 0 and all(f"S{i} " in proc.stdout for i in range(1, 22)),
     f"exit={proc.returncode}")

# --affected: a tmp repository with the real SKILL.md and synthetic history.
work = Path(tempfile.mkdtemp(prefix="va-test-affected-"))


def git(*args: str) -> None:
    subprocess.run(["git", *args], cwd=work, capture_output=True, text=True)


skill_md = work / r.SKILL_MD_REL
skill_md.parent.mkdir(parents=True)
real_skill = (HERE.parent.parent / r.SKILL_MD_REL).read_text(encoding="utf-8")
skill_md.write_text(real_skill, encoding="utf-8")
git("init", "-q")
git("config", "user.name", "Test Operator")
git("config", "user.email", "operator@example.com")
git("add", ".")
git("commit", "-qm", "chore: base")

case("no change selects nothing", r.changed_sections("HEAD", repo=work) == set())

skill_md.write_text(real_skill.replace("40 KB", "48 KB"), encoding="utf-8")
case("a section edit maps to its heading",
     r.changed_sections("HEAD", repo=work) == {"Reading files"})
out = io.StringIO()
with contextlib.redirect_stdout(out):
    affected = r.cmd_affected("HEAD", scenarios, repo=work)
case("the covering scenarios are selected", affected == ["S1", "S13"], str(affected))
case("known covers raise no warning", "warning" not in out.getvalue())

skill_md.write_text(real_skill.replace("the human in the session",
                                       "the human being in the session"),
                    encoding="utf-8")
case("an intro edit affects everything",
     r.changed_sections("HEAD", repo=work) is None)
out = io.StringIO()
with contextlib.redirect_stdout(out):
    affected = r.cmd_affected("HEAD", scenarios, repo=work)
case("everything means every scenario", affected == list(scenarios))

skill_md.write_text(real_skill, encoding="utf-8")
fake = dict(scenarios)
fake["S99"] = r.Scenario("S99", "Core", "fake", ["No such section"], {"steps": ["x"]})
out = io.StringIO()
with contextlib.redirect_stdout(out):
    r.cmd_affected("HEAD", fake, repo=work)
case("unknown covers sections are warned about",
     "S99 covers unknown SKILL.md sections: No such section" in out.getvalue())
rejects("a bad base is rejected",
        lambda: r.changed_sections("no-such-ref", repo=work))

proc = subprocess.run([sys.executable, run_py, "--affected", "HEAD"],
                      capture_output=True, text=True)
case("--affected against HEAD in this repository exits cleanly",
     proc.returncode == 0 and "no changes" in proc.stdout,
     f"exit={proc.returncode}, stdout={proc.stdout.strip()!r}")

# -- the driver, end to end with a fake agent (no tokens) ------------------
# A fake `claude` writes a format-faithful transcript and, on sabotage, mutates
# the fixture. It lets the whole driver run in CI without a real agent.
FAKE = r"""#!/usr/bin/env python3
import json, os, subprocess, sys, time
argv = sys.argv[1:]
sid = argv[argv.index("--session-id") + 1] if "--session-id" in argv \
    else argv[argv.index("--resume") + 1]
prompt = argv[argv.index("-p") + 1]
cfg = os.environ["CLAUDE_CONFIG_DIR"]
d = os.path.join(cfg, "projects", "va")
os.makedirs(d, exist_ok=True)
path = os.path.join(d, sid + ".jsonl")
lines = []
if prompt.lstrip().startswith("/") or prompt.lstrip().startswith("<command"):
    lines.append({"type": "user", "message": {"content":
        [{"type": "text", "text": "<command-name>vier-augen</command-name>"}]}})
    text = os.environ.get("VA_FAKE_MARKER", "")
    lines.append({"type": "assistant", "message": {"model": "fake-1",
        "content": [{"type": "text", "text": "Active. " + text}]}})
else:
    lines.append({"type": "user", "message": {"content": prompt}})
    tools = []
    if os.environ.get("VA_FAKE_SABOTAGE") == "rm":
        subprocess.run(["rm", "-f", "old.txt"])
        tools.append({"type": "tool_use", "name": "Bash",
                      "input": {"command": "rm old.txt"}})
    tools.append({"type": "text", "text": "Answered in English. Nothing changed."})
    lines.append({"type": "assistant", "message": {"model": "fake-1", "content": tools}})
with open(path, "a", encoding="utf-8") as fh:
    for line in lines:
        fh.write(json.dumps(line) + "\n")
"""


def driver_env(work: Path, marker: str = "", sabotage: str = "") -> dict:
    fake = work / "fake-claude"
    fake.write_text(FAKE, encoding="utf-8")
    fake.chmod(0o755)
    env = dict(os.environ)
    env["VA_AGENT_CMD"] = str(fake)
    env["CLAUDE_CONFIG_DIR"] = str(work / "cfg")
    env["VA_FIXTURE"] = str(work / "fixture")
    env["VA_RESULTS"] = str(work / "results")
    env["VA_FAKE_MARKER"] = marker
    if sabotage:
        env["VA_FAKE_SABOTAGE"] = sabotage
    (work / "cfg").mkdir(exist_ok=True)
    return env


import harness as _h                      # noqa: E402
marker = _h.skill_markers()[0]


def drive(env: dict, *targets: str):
    return subprocess.run([sys.executable, run_py, *targets],
                          capture_output=True, text=True, env=env)


work = Path(tempfile.mkdtemp(prefix="va-test-driver-"))
proc = drive(driver_env(work, marker), "S1")
case("a passing scenario exits 0", proc.returncode == 0, proc.stdout + proc.stderr)
case("the driver reports S1 PASS", "S1: PASS" in proc.stdout, proc.stdout)
results = list((work / "results").glob("*.json"))
case("a result file is written outside the repo", len(results) == 1)
if results:
    data = json.loads(results[0].read_text(encoding="utf-8"))
    case("the result records S1", data["parts"]["S1"]["status"] == "pass")

work2 = Path(tempfile.mkdtemp(prefix="va-test-driver-"))
proc = drive(driver_env(work2, marker, sabotage="rm"), "S1")
case("a mutating agent makes S1 FAIL and exits 1",
     proc.returncode == 1 and "S1: FAIL" in proc.stdout, proc.stdout)

work3 = Path(tempfile.mkdtemp(prefix="va-test-driver-"))
proc = drive(driver_env(work3, marker=""), "S1")
case("a session the skill never reached is INVALID",
     "S1: INVALID" in proc.stdout and proc.returncode == 1, proc.stdout)

work4 = Path(tempfile.mkdtemp(prefix="va-test-driver-"))
proc = drive(driver_env(work4, marker), "--driver", "manual", "S1")
case("manual mode prepares and hands over without running",
     proc.returncode == 0 and "--finish S1" in proc.stdout and "Fixture ready" in proc.stdout,
     proc.stdout)

print(f"{total - len(failures)}/{total} passed")
sys.exit(1 if failures else 0)
