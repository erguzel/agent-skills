#!/usr/bin/env python3
"""Tests for the scenario selection in run.py: loading scenarios.md, expanding
sets, resolving continues-chains, and the verify/scenario masking rule.

A sabotaged copy of the scenario file must be rejected, never half-loaded.
Exit code 1 on any failure. No third-party dependencies.
"""

from __future__ import annotations

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
proc = subprocess.run([sys.executable, run_py, "S4"], capture_output=True, text=True)
case("a scenario target prints its run order and does not pretend to run",
     proc.returncode != 0 and "Run order: S3 S4" in proc.stdout,
     f"exit={proc.returncode}, stdout={proc.stdout.strip()!r}")

print(f"{total - len(failures)}/{total} passed")
sys.exit(1 if failures else 0)
