#!/usr/bin/env python3
"""Tests for the vier-augen attribution patterns.

- Runs hooks/commit-msg against messages and author/committer identities that
  must be rejected or accepted.
- Checks that the patterns embedded in ci/vier-augen.yml are identical to
  hooks/attribution/*.ere.

Exit code 1 on any failure. Needs git and a POSIX sh. No third-party dependencies.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent / "skills" / "vier-augen"
HOOK = SKILL / "hooks" / "commit-msg"
PATTERNS = SKILL / "hooks" / "attribution"
CI_TEMPLATE = SKILL / "ci" / "vier-augen.yml"

HUMAN = ("Jane Doe", "jane@example.com")

BLOCK_MESSAGES = [
    "feat: x\n\nCo-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>",
    "feat: x\n\nCo-Authored-By: Claude Code <noreply@anthropic.com>",
    "fix: y\n\nClaude-Session: https://claude.ai/code/session_018TfNsxx6hg",
    "docs: z\n\n\U0001f916 Generated with [Claude Code](https://claude.com/claude-code)",
    "feat: a\n\nCo-authored-by: Codex <noreply@openai.com>",
    "feat: a\n\nTask: https://chatgpt.com/codex/tasks/task_e_123",
    "feat: b\n\nCo-authored-by: Copilot <copilot@github.com>",
    "feat: b\n\nCo-authored-by: Copilot <198982749+Copilot@users.noreply.github.com>",
    "feat: c\n\nCo-authored-by: Cursor Agent <cursoragent@cursor.com>",
    "feat: d\n\nMade-with: Cursor",
    "feat: e\n\nCo-authored-by: aider (anthropic/claude-sonnet-4) <aider@aider.chat>",
    "aider: fix the parser",
    "feat: f\n\nAmp-Thread-ID: https://ampcode.com/threads/T-123",
    "feat: f\n\nCo-authored-by: Amp <amp@ampcode.com>",
    "feat: g\n\nCo-Authored-By: opencode <noreply@opencode.ai>",
    "feat: g\n\nGenerated with opencode",
    "feat: h\n\nCo-authored-by: devin-ai-integration[bot] <1+devin-ai-integration[bot]@users.noreply.github.com>",
]

PASS_MESSAGES = [
    "feat: add parser",
    "fix: typo\n\nCo-authored-by: Claude Monet <claude.monet@example.com>",
    "chore: bump deps\n\nCo-authored-by: Jane Doe <jane@example.com>",
    "docs: explain how Claude Code attribution works",
    "docs: note that the site is generated with [mkdocs](https://www.mkdocs.org)",
    "feat: cursor movement\n\nMade with love",
    "fix: amplifier thread pool",
    "feat: x\n\n# Co-Authored-By: Claude <noreply@anthropic.com>",
]

BLOCK_IDENTITIES = [
    ("claude[bot]", "41898282+claude[bot]@users.noreply.github.com"),
    ("copilot-swe-agent[bot]", "198982749+Copilot@users.noreply.github.com"),
    ("Devin AI", "158243242+devin-ai-integration[bot]@users.noreply.github.com"),
    ("google-labs-jules[bot]", "161369871+google-labs-jules[bot]@users.noreply.github.com"),
    ("Jane Doe (aider)", "jane@example.com"),
    ("Claude", "noreply@anthropic.com"),
    ("Codex", "noreply@openai.com"),
]

PASS_IDENTITIES = [
    ("Claude Shannon", "claude@example.com"),
    ("dependabot[bot]", "49699333+dependabot[bot]@users.noreply.github.com"),
    ("Jane Doe", "1234+jane@users.noreply.github.com"),
    ("Amp Team", "team@example.com"),
]


def run_hook(repo: Path, message: str, author: tuple[str, str]) -> int:
    msg_file = repo / "MSG"
    msg_file.write_text(message + "\n", encoding="utf-8")
    env = dict(os.environ,
               GIT_AUTHOR_NAME=author[0], GIT_AUTHOR_EMAIL=author[1],
               GIT_COMMITTER_NAME=author[0], GIT_COMMITTER_EMAIL=author[1])
    result = subprocess.run(["sh", str(HOOK), str(msg_file)], cwd=repo, env=env,
                            capture_output=True, text=True)
    return result.returncode


def embedded(marker: str, text: str) -> str:
    match = re.search(rf"<<'{marker}'\n(.*?)\n\s*{marker}\n", text, re.DOTALL)
    if not match:
        return ""
    lines = match.group(1).split("\n")
    return "\n".join(line[10:] if line.startswith(" " * 10) else line for line in lines) + "\n"


def main() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        subprocess.run(["git", "init", "-q", str(repo)], check=True)

        for message in BLOCK_MESSAGES:
            if run_hook(repo, message, HUMAN) == 0:
                failures.append(f"not blocked: message {message!r}")
        for message in PASS_MESSAGES:
            if run_hook(repo, message, HUMAN) != 0:
                failures.append(f"false positive: message {message!r}")
        for ident in BLOCK_IDENTITIES:
            if run_hook(repo, "feat: ok", ident) == 0:
                failures.append(f"not blocked: identity {ident!r}")
        for ident in PASS_IDENTITIES:
            if run_hook(repo, "feat: ok", ident) != 0:
                failures.append(f"false positive: identity {ident!r}")

    template = CI_TEMPLATE.read_text(encoding="utf-8")
    for name, marker in (("message.ere", "VIER_AUGEN_MESSAGE"),
                         ("identity.ere", "VIER_AUGEN_IDENTITY")):
        if embedded(marker, template) != (PATTERNS / name).read_text(encoding="utf-8"):
            failures.append(f"ci/vier-augen.yml: embedded {name} differs from hooks/attribution/{name}")

    total = (len(BLOCK_MESSAGES) + len(PASS_MESSAGES)
             + len(BLOCK_IDENTITIES) + len(PASS_IDENTITIES) + 2)
    for failure in failures:
        print(f"FAIL {failure}")
    print(f"{total - len(failures)}/{total} checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
