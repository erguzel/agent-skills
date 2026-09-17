"""Agent profile: Claude Code.

A profile tells the harness how to start the agent, where the skill has to be
linked, how the operator invokes it, and how to read the session afterwards.
The transcript format is internal to Claude Code and changes between versions;
when it cannot be read, the harness reports "undetermined", never "pass".
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import harness as h

NAME = "claude-code"
SKILL_DIRS = [".claude/skills"]
INVOKE = "/vier-augen"


def command() -> str:
    return os.environ.get("VA_AGENT_CMD", "claude")


def launch_argv(session_id: str, headless_prompt: Optional[str] = None) -> List[str]:
    argv = [command(), "--session-id", session_id]
    if headless_prompt is not None:
        argv += ["-p", headless_prompt]
    return argv


def config_dir(env: Dict[str, str]) -> Path:
    return Path(env.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def preflight(env: Dict[str, str]) -> Tuple[List[str], List[str], str]:
    """Errors stop the run; warnings are shown and recorded."""
    errors, warnings = [], []
    cfg = config_dir(env)
    label = "isolated" if env.get("CLAUDE_CONFIG_DIR") else "user"
    settings = cfg / "settings.json"
    if settings.is_file():
        text = settings.read_text(encoding="utf-8", errors="replace")
        if "guard.py" in text or "vier-augen" in text:
            errors.append(f"{settings} references the vier-augen adapter; it would mask "
                          "the text-only behaviour. Remove it for the test, or use --isolated.")
        try:
            allow = json.loads(text).get("permissions", {}).get("allow", [])
        except ValueError:
            allow = []
        if allow:
            warnings.append(f"{settings} has allow rules ({len(allow)}); the runtime may not "
                            "prompt for some actions. Attempts are still recorded.")
            label += "+allow-rules"
    if (cfg / "CLAUDE.md").is_file():
        warnings.append(f"{cfg / 'CLAUDE.md'} is present; personal instructions can colour "
                        "the result. Consider --isolated or moving it aside.")
        label += "+CLAUDE.md"
    if (cfg / "skills" / "vier-augen").exists():
        warnings.append(f"{cfg / 'skills' / 'vier-augen'} exists; the session may load that "
                        "copy instead of this repository's.")
    return errors, warnings, label


def find_transcript(session_id: str, env: Dict[str, str]) -> Optional[Path]:
    matches = sorted((config_dir(env) / "projects").glob(f"*/{session_id}.jsonl"))
    return matches[-1] if matches else None


def _blocks(content) -> list:
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return content if isinstance(content, list) else []


def load_transcript(session_id: str, env: Dict[str, str]) -> Optional[h.Transcript]:
    path = find_transcript(session_id, env)
    if path is None:
        return None
    raw = path.read_text(encoding="utf-8", errors="replace")
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
                    events.append(h.Event("user", text=str(block.get("text", ""))))
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
