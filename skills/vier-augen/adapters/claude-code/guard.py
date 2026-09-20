#!/usr/bin/env python3
"""vier-augen PreToolUse guard for Claude Code.

Reads the hook input on stdin, asks the skill's command classifier what each
command in a Bash call does, and answers in Claude Code's terms:

- An Operator-tier step gets an "ask" decision, so a human approves it.
  Approving the prompt is how the operator hands the step over.
- A rewrite of published history (force-push) is blocked (exit 2). Run it
  yourself if you mean it.
- Everything else gets no decision; the normal permission flow applies.

The classifier is `lib/tiers.py`, two directories up in the skill folder, and
this file does not work copied out on its own. If the classifier cannot be
found, the guard says so on stderr and asks for every command rather than
letting them through.

Not a security boundary: a determined command can still evade text matching.
"""
import importlib.util
import json
import sys
from pathlib import Path

TIERS = Path(__file__).resolve().parents[2] / "lib" / "tiers.py"


def load_tiers():
    try:
        spec = importlib.util.spec_from_file_location("vier_augen_tiers", TIERS)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception:           # missing, unreadable or broken: treated alike
        return None


def ask(reason):
    json.dump({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "ask",
        "permissionDecisionReason": f"vier-augen: {reason}",
    }}, sys.stdout)


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    if data.get("tool_name") != "Bash":
        return 0
    command = (data.get("tool_input") or {}).get("command") or ""

    tiers = load_tiers()
    if tiers is None:
        print(f"vier-augen: the command classifier was not found at {TIERS}; asking "
              "for every command until it is. The guard needs the whole skill folder "
              "around it, not this file alone.", file=sys.stderr)
        ask("the command classifier is missing, so every command is asked about")
        return 0

    decisions = tiers.check_command(command)
    rewrites = [reason for tier, reason in decisions if tier == tiers.REWRITE]
    if rewrites:
        print(f"vier-augen: blocked - {rewrites[0]}. Run it yourself if you mean it.",
              file=sys.stderr)
        return 2
    if decisions:
        reasons = "; ".join(dict.fromkeys(reason for _, reason in decisions))
        ask(f"{reasons}. Approving hands this step to the agent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
