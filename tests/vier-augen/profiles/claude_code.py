"""Agent profile: Claude Code.

Everything the harness needs that is specific to one agent lives in a profile:
how to launch it, where the skill is linked, how the operator invokes it, which
tool names write or only read, and how to read the transcript afterwards. The
harness itself is agent-neutral, so a second agent is a second profile beside
this one - it is the seam the architecture keeps open (see the README).

The transcript format is internal to Claude Code and changes between versions;
when it cannot be read the harness reports "undetermined", never "pass".
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import harness as h

NAME = "claude-code"
SKILL_DIRS = [".claude/skills"]          # where build-fixture links the skill
INVOKE = "/vier-augen"

# Tool names, the one place they belong. Anything not listed counts as unknown,
# and a write/delete check that meets an unknown tool is undetermined, not passed.
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
READ_TOOLS = {"Read", "NotebookRead"}
SAFE_TOOLS = READ_TOOLS | {
    "Grep", "Glob", "LS", "WebFetch", "WebSearch", "TodoWrite", "TodoRead",
    "Skill", "SlashCommand", "Task", "Agent", "ToolSearch", "AskUserQuestion",
    "BashOutput", "KillShell", "ExitPlanMode", "EnterPlanMode",
    "ListMcpResourcesTool", "ReadMcpResourceTool",
}


def command() -> str:
    return os.environ.get("VA_AGENT_CMD", "claude")


def launch_argv(session_id: str, prompt: str, resume: bool = False) -> list[str]:
    """One headless turn. The first turn opens the session; later ones resume it."""
    if resume:
        return [command(), "--resume", session_id, "-p", prompt,
                "--permission-mode", "bypassPermissions"]
    return [command(), "--session-id", session_id, "-p", prompt,
            "--permission-mode", "bypassPermissions"]


def config_dir(env: dict) -> Path:
    return Path(env.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def preflight(env: dict) -> tuple[list[str], list[str], str]:
    """Errors stop a run; warnings are shown and recorded. Guards the masking rule."""
    errors, warnings = [], []
    cfg = config_dir(env)
    label = "isolated" if env.get("CLAUDE_CONFIG_DIR") else "user"
    settings = cfg / "settings.json"
    if settings.is_file():
        text = settings.read_text(encoding="utf-8", errors="replace")
        if "guard.py" in text or "vier-augen" in text:
            errors.append(f"{settings} references the vier-augen adapter; it would mask "
                          "the text-only behaviour. Remove it for the test, or use --isolated.")
    if (cfg / "CLAUDE.md").is_file():
        warnings.append(f"{cfg / 'CLAUDE.md'} is present; personal instructions can colour "
                        "the result. Move it aside, or use --isolated.")
        label += "+CLAUDE.md"
    return errors, warnings, label


def find_transcript(session_id: str, env: dict) -> Optional[Path]:
    matches = sorted((config_dir(env) / "projects").glob(f"*/{session_id}.jsonl"))
    return matches[-1] if matches else None


def _blocks(content) -> list:
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return content if isinstance(content, list) else []


def parse_transcript(raw: str) -> h.Transcript:
    """Turn Claude Code's JSONL into the harness's agent-neutral event list."""
    events, model = [], None
    for line in raw.splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        message = entry.get("message") or {}
        if entry.get("type") == "user":
            for block in _blocks(message.get("content")):
                if isinstance(block, dict) and block.get("type") == "text":
                    text = str(block.get("text", ""))
                    if not text.lstrip().startswith("<command-"):
                        events.append(h.Event("user", text=text))
        elif entry.get("type") == "assistant":
            model = message.get("model") or model
            for block in _blocks(message.get("content")):
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    events.append(h.Event("text", text=str(block.get("text", ""))))
                elif block.get("type") == "tool_use":
                    events.append(h.Event("tool", name=str(block.get("name", "")),
                                          input=block.get("input") or {}))
    return h.Transcript(events=events, raw=raw, model=model)


def load_transcript(session_id: str, env: dict) -> Optional[h.Transcript]:
    path = find_transcript(session_id, env)
    if path is None:
        return None
    return parse_transcript(path.read_text(encoding="utf-8", errors="replace"))
