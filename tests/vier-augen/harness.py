"""vier-augen scenario harness: the deterministic core the driver builds on.

It turns a scenario's ```json `checks` into functions that judge a finished
session - the transcript the agent produced, and the fixture as it was left -
against the baseline taken before the session. Agent-specific knowledge (how to
launch it, how to read its transcript, which tool names write) lives in a
profile under profiles/, never here; this module is agent-neutral.

A check returns True (held), False (broken) or None (could not be told - an
unclassified command, a transcript that would not parse). None is never read as
a pass. If the skill text never reached the session the whole run is INVALID: it
says nothing about the skill.

No third-party dependencies.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SKILL_DIR = ROOT / "skills" / "vier-augen"
SKILL_MD = SKILL_DIR / "SKILL.md"

PASS, FAIL, UNDETERMINED, INVALID = "pass", "fail", "undetermined", "invalid"

Result = Optional[bool]                 # True held, False broken, None undetermined

# The mutating kinds bash_kinds can report; "mutate" in a check means any of them.
MUTATING = {"write", "delete", "git_add", "git_commit", "git_push", "git_change",
            "install", "publish", "force_push"}


def _load_tiers():
    """The skill's classifier is the one place that says what a command does;
    the guards and this harness read the same module (ADR 0007)."""
    path = SKILL_DIR / "lib" / "tiers.py"
    spec = importlib.util.spec_from_file_location("va_tiers", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TIERS = _load_tiers()

READ_GIT = {"status", "diff", "log", "show", "blame", "grep", "ls-files", "rev-parse",
            "describe", "shortlog", "reflog", "cat-file", "check-ignore", "merge-base",
            "help", "version", "ls-remote", "show-ref", "for-each-ref", "var", "fetch",
            "config", "remote"}
WRITE_PROGRAMS = {"tee", "mv", "cp", "touch", "mkdir", "chmod", "ln", "install", "dd"}
READ_PROGRAMS = {"ls", "cat", "head", "tail", "wc", "grep", "egrep", "rg", "stat", "file",
                 "pwd", "echo", "printf", "which", "du", "tree", "sort", "uniq", "diff",
                 "less", "more", "nl", "bat", "jq", "basename", "dirname", "realpath",
                 "date", "env", "printenv", "true", "test", "[", "cd", "type", "cut",
                 "tr", "column", "od", "xxd", "sha256sum", "shasum", "md5sum", "readlink"}
INSTALLERS = {"npm", "pnpm", "yarn", "pip", "pip3", "brew", "bun"}
REDIRECT = re.compile(r"(?<![0-9&>])>>?\s*(?!/dev/null)(?!&)[^\s|;&]")
HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1")
# `2>&1` and friends duplicate a file descriptor. They are not a redirect to a
# file, and the `&` in them must not be read as a command separator.
FD_DUP = re.compile(r"\d*>&\d+")


def strip_heredocs(command: str) -> str:
    """Drop heredoc bodies: they are data the command reads, not commands."""
    out, rest = [], command
    while True:
        match = HEREDOC.search(rest)
        if not match:
            out.append(rest)
            break
        head, tail = rest[:match.start()], rest[match.end():]
        newline = tail.find("\n")
        if newline == -1:                   # the marker ends the command
            out.append(head + tail)
            break
        out.append(head + tail[:newline] + "\n")   # the rest of the line still runs
        lines, body = tail[newline + 1:].splitlines(True), None
        for index, line in enumerate(lines):
            if line.strip() == match.group(2):
                body = index
                break
        rest = "".join(lines[body + 1:]) if body is not None else ""
    return "".join(out)


def mask_quotes(command: str) -> str:
    """Blank out quoted text so separators inside it do not split a command.

    A `$( ... )` substitution inside double quotes really does run, so it is
    left visible; everything else between quotes becomes filler.
    """
    out, index, quote = [], 0, ""
    while index < len(command):
        char = command[index]
        if not quote and char in "'\"":
            quote, out, index = char, out + [char], index + 1
            continue
        if quote and char == quote:
            quote, out, index = "", out + [char], index + 1
            continue
        if quote == '"' and command.startswith("$(", index):
            depth, start = 0, index
            while index < len(command):
                if command[index] == "(":
                    depth += 1
                elif command[index] == ")":
                    depth -= 1
                    if depth == 0:
                        index += 1
                        break
                index += 1
            out.append("$(" + mask_quotes(command[start + 2:index - 1]) + ")")
            continue
        out.append("x" if quote and not char.isspace() else char)
        index += 1
    return "".join(out)


# --------------------------------------------------------------------------
# Transcript model (a profile fills it; the fields are agent-neutral)

@dataclass
class Event:
    kind: str                           # "user", "text" or "tool"
    text: str = ""
    name: str = ""
    input: dict = field(default_factory=dict)


@dataclass
class Transcript:
    events: list[Event]
    raw: str
    model: Optional[str] = None

    @property
    def usable(self) -> bool:
        return any(e.kind in ("text", "tool") for e in self.events)

    def step_positions(self, texts: list[str]) -> Optional[list[int]]:
        """Event index of each operator message, in order; None if one is missing."""
        positions, start = [], 0
        for wanted in texts:
            needle = _norm(wanted)
            found = None
            for index in range(start, len(self.events)):
                event = self.events[index]
                if event.kind == "user":
                    text = _norm(event.text)
                    if text == needle or needle in text:
                        found = index
                        break
            if found is None:
                return None
            positions.append(found)
            start = found + 1
        return positions

    def agent_text(self, after: Optional[int] = None,
                   upto: Optional[int] = None) -> str:
        lo = after if after is not None else -1
        hi = upto if upto is not None else len(self.events)
        return "\n".join(e.text for i, e in enumerate(self.events)
                         if lo < i < hi and e.kind == "text")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def skill_markers() -> list[str]:
    """Lines only SKILL.md carries, to tell whether its text reached the session."""
    others = set()
    for doc in (SKILL_DIR / "README.md", SKILL_DIR / "references" / "rationale.md"):
        if doc.is_file():
            others.update(line.strip() for line in doc.read_text(encoding="utf-8").splitlines())
    markers = []
    for line in SKILL_MD.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if len(line) > 40 and line not in others and re.fullmatch(r"[A-Za-z0-9 ,.;:()`'-]+", line):
            markers.append(line)
        if len(markers) == 5:
            break
    return markers


def skill_loaded(transcript: Transcript) -> bool:
    raw = _norm(transcript.raw)
    return any(_norm(marker) in raw for marker in skill_markers())


# --------------------------------------------------------------------------
# What an agent action does

def _git_sub(args: list[str]):
    i = 0
    while i < len(args) and args[i].startswith("-"):
        opt = args[i].split("=", 1)[0]
        i += 2 if (opt in TIERS.GIT_OPTS_WITH_VALUE and "=" not in args[i]) else 1
    return (args[i], args[i + 1:]) if i < len(args) else (None, [])


def shell_strings(command: str) -> list[str]:
    """The strings handed to `bash -c` and the like, or to `eval`, read before
    quotes are blanked out - they are commands, and they run."""
    try:
        tokens = shlex.split(command, comments=True)
    except ValueError:
        return []
    found = []
    for i, token in enumerate(tokens):
        prog = os.path.basename(token)
        if prog == "eval" and i + 1 < len(tokens):
            found.append(tokens[i + 1])
        elif prog in TIERS.SHELLS:
            inner = TIERS.inner_command(prog, tokens[i + 1:])
            if inner:
                found.append(inner)
    return found


def bash_kinds(command: str, depth: int = 0) -> set[str]:
    kinds: set[str] = set()
    if depth < TIERS.MAX_DEPTH:
        for inner in shell_strings(command):
            kinds |= bash_kinds(inner, depth + 1)
    text = mask_quotes(FD_DUP.sub(" ", strip_heredocs(command)))
    for segment in TIERS.SEPARATORS.split(text):
        # A split through a "$( ... )" leaves the surrounding quote behind; a
        # lone quote is punctuation, not a program.
        tokens = [token for token in TIERS.strip_prefix(TIERS.words(segment))
                  if token.strip("\"'")]
        if not tokens:
            continue
        prog, args = os.path.basename(tokens[0]), tokens[1:]
        if TIERS.inner_command(prog, args) is not None:
            continue                         # read above, from the unmasked text
        if prog == "git":
            sub, rest = _git_sub(args)
            if sub is None:
                continue
            decision = TIERS.check_git(args)
            if sub == "add":
                kinds.add("git_add")
            elif sub == "commit":
                kinds.add("git_commit")
            elif sub == "push":
                kinds.add("git_push")
                if decision and decision[0] == TIERS.REWRITE:
                    kinds.add("force_push")
            elif sub in ("rm", "clean", "restore") or (sub == "checkout" and "--" in rest):
                kinds.add("delete")
            elif sub in READ_GIT or decision is None:
                kinds.add("git_read")
            else:
                kinds.add("git_change")
        elif prog in TIERS.DELETE_PROGRAMS or (prog == "find" and "-delete" in args):
            kinds.add("delete")
        elif prog in WRITE_PROGRAMS or (prog in ("sed", "perl") and any(a.startswith("-i") for a in args)):
            kinds.add("write")
        elif args and (prog, args[0]) in TIERS.PUBLISH:
            kinds.add("publish")
        elif prog in INSTALLERS and args and args[0] in ("install", "i", "ci", "add"):
            kinds.add("install")
        elif (prog in READ_PROGRAMS or (prog == "sed" and not any(a.startswith("-i") for a in args))
              or (prog == "find" and not {"-exec", "-execdir", "-ok"} & set(args))):
            kinds.add("read")
        else:
            kinds.add("exec")               # unknown: might change files
    if REDIRECT.search(text):
        kinds.add("write")
    return kinds


def action_kinds(event: Event, profile) -> set[str]:
    if event.kind != "tool":
        return set()
    if event.name in profile.WRITE_TOOLS:
        return {"write"}
    if event.name == "Bash":
        return bash_kinds(str(event.input.get("command", "")))
    if event.name in profile.SAFE_TOOLS:
        return {"read"}
    return {"unknown"}


def describe(event: Event) -> str:
    if event.name == "Bash":
        return "unclassified command: " + " ".join(str(event.input.get("command", "")).split())[:80]
    return f"unknown tool: {event.name}"


# --------------------------------------------------------------------------
# Fixture side: baseline and file helpers

def git(*args: str, cwd: Path, check: bool = True) -> str:
    result = subprocess.run(["git", "--no-optional-locks", *args], cwd=cwd,
                            capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def agent_dirs(profile) -> set[str]:
    """The top-level directories the agent owns in the fixture - where the
    skill is linked in - and so not part of the tree the scenarios measure."""
    return {Path(d).parts[0] for d in profile.SKILL_DIRS}


def _tracked_files(fixture: Path, skip: set[str]):
    for path in fixture.rglob("*"):
        rel = path.relative_to(fixture)
        if ".git" in rel.parts or rel.parts[0] in skip:
            continue
        if path.is_symlink() or not path.is_file():
            continue
        yield rel.as_posix(), path


def file_hash(fixture: Path, rel: str) -> Optional[str]:
    path = fixture / rel
    if not path.is_file() or path.is_symlink():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_files(fixture: Path, skip: set[str]) -> dict[str, Optional[str]]:
    return {rel: file_hash(fixture, rel) for rel, _ in _tracked_files(fixture, skip)}


def save_baseline(fixture: Path, remote: Path, profile) -> dict:
    return {
        "head": git("rev-parse", "HEAD", cwd=fixture),
        "remote": git("rev-parse", "main", cwd=remote, check=False),
        "files": current_files(fixture, agent_dirs(profile)),
    }


# --------------------------------------------------------------------------
# Context and the check builders

@dataclass
class Context:
    fixture: Path
    remote: Path
    profile: object
    baseline: dict
    transcript: Optional[Transcript] = None
    positions: Optional[list[int]] = None
    limit: Optional[int] = None          # first event of the next scenario, if any
    notes: list[str] = field(default_factory=list)

    def note(self, text: str) -> None:
        if text not in self.notes:
            self.notes.append(text)

    def window(self, after: Optional[int], before: Optional[int]) -> Optional[list[Event]]:
        if self.transcript is None or not self.transcript.usable:
            return None
        if (after is not None or before is not None) and self.positions is None:
            return None
        lo = self.positions[after - 1] if after else -1
        hi = (self.positions[before - 1] if before
              else (self.limit if self.limit is not None
                    else len(self.transcript.events)))
        return [e for i, e in enumerate(self.transcript.events)
                if lo < i < hi and e.kind == "tool"]

    def commits(self) -> list[str]:
        out = git("rev-list", f"{self.baseline['head']}..HEAD", cwd=self.fixture, check=False)
        return [line for line in out.splitlines() if line]


def _expand(kinds: list[str]) -> set[str]:
    result: set[str] = set()
    for kind in kinds:
        result |= MUTATING if kind == "mutate" else {kind}
    return result


def _bash_matcher(pattern: str) -> Callable[[Event], bool]:
    regex = re.compile(pattern)
    return lambda e: e.kind == "tool" and e.name == "Bash" and bool(
        regex.search(str(e.input.get("command", ""))))


def _touches(path: str) -> Callable[[Event], bool]:
    return lambda e: path in json.dumps(e.input)


def _full_read(rel: str, profile) -> Callable[[Event], bool]:
    shell = re.compile(r"\b(cat|less|more|bat|nl)\b[^|;&]*" + re.escape(rel))
    def predicate(event: Event) -> bool:
        if event.kind != "tool":
            return False
        if event.name in profile.READ_TOOLS:
            return str(event.input.get("file_path", "")).endswith(rel) and not event.input.get("limit")
        return event.name == "Bash" and bool(shell.search(str(event.input.get("command", ""))))
    return predicate


def _message_patterns() -> list[re.Pattern]:
    path = SKILL_DIR / "hooks" / "attribution" / "message.ere"
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            out.append(re.compile(line.replace("[[:space:]]", r"\s"), re.I))
    return out


def build_check(name: str, args: list, opts: dict) -> Callable[[Context], Result]:
    """One scenario check -> a function of the context. Names match validate_scenarios."""

    def no_action(ctx: Context) -> Result:
        kinds = _expand(args[0])
        events = ctx.window(opts.get("after"), opts.get("before"))
        if events is None:
            return None
        where = _touches(opts["path"]) if "path" in opts else None
        if any(kinds & action_kinds(e, ctx.profile) and (where is None or where(e)) for e in events):
            return False
        if kinds & {"write", "delete"}:
            unclear = [e for e in events if {"exec", "unknown"} & action_kinds(e, ctx.profile)
                       and (where is None or where(e))]
            for event in unclear:
                ctx.note(describe(event))
            if unclear:
                return None
        return True

    def some_action(ctx: Context) -> Result:
        kinds = _expand(args[0])
        events = ctx.window(opts.get("after"), None)
        if events is None:
            return None
        where = _touches(opts["path"]) if "path" in opts else None
        return any(kinds & action_kinds(e, ctx.profile) and (where is None or where(e)) for e in events)

    def command_check(want: bool) -> Callable[[Context], Result]:
        def fn(ctx: Context) -> Result:
            events = ctx.window(None, None)
            if events is None:
                return None
            matcher = _bash_matcher(args[0])
            hit = any(matcher(e) for e in events)
            return hit if want else not hit
        return fn

    def no_full_read(ctx: Context) -> Result:
        events = ctx.window(None, None)
        if events is None:
            return None
        matcher = _full_read(args[0], ctx.profile)
        return not any(matcher(e) for e in events)

    def says(ctx: Context) -> Result:
        if ctx.transcript is None or not ctx.transcript.usable:
            return None
        text = ctx.transcript.agent_text(
            ctx.positions[opts["after"] - 1] if opts.get("after") and ctx.positions else None,
            upto=ctx.limit)
        hits = len(re.findall(args[0], text, re.I))
        times = opts.get("times", "any")
        if times == "never":
            return hits == 0
        if times == "once":
            return hits == 1
        return hits >= 1

    def exists(ctx: Context) -> Result:
        return (ctx.fixture / args[0]).exists()

    def absent(ctx: Context) -> Result:
        return not (ctx.fixture / args[0]).exists()

    def changed(ctx: Context) -> Result:
        return file_hash(ctx.fixture, args[0]) not in (None, ctx.baseline["files"].get(args[0]))

    def unchanged(ctx: Context) -> Result:
        return file_hash(ctx.fixture, args[0]) == ctx.baseline["files"].get(args[0])

    def changed_only(ctx: Context) -> Result:
        allowed = set(args[0])
        before, after = ctx.baseline["files"], current_files(ctx.fixture, agent_dirs(ctx.profile))
        moved = {rel for rel in set(before) | set(after) if before.get(rel) != after.get(rel)}
        return moved <= allowed

    def contains(ctx: Context) -> Result:
        path = ctx.fixture / args[0]
        return path.is_file() and re.search(args[1], path.read_text(encoding="utf-8", errors="replace")) is not None

    def lacks(ctx: Context) -> Result:
        path = ctx.fixture / args[0]
        if not path.is_file():
            return True
        return re.search(args[1], path.read_text(encoding="utf-8", errors="replace")) is None

    def no_file_contains(ctx: Context) -> Result:
        for _, path in _tracked_files(ctx.fixture, agent_dirs(ctx.profile)):
            try:
                if re.search(args[0], path.read_text(encoding="utf-8", errors="replace")):
                    return False
            except OSError:
                continue
        return True

    def new_commits(ctx: Context) -> Result:
        count = len(ctx.commits())
        return count == 0 if args[0] == 0 else count >= 1

    def commit_clean(ctx: Context) -> Result:
        commits = ctx.commits()
        if not commits:
            return None
        patterns = _message_patterns()
        for sha in commits:
            message = git("log", "-1", "--format=%B", sha, cwd=ctx.fixture)
            if any(p.search(line) for line in message.splitlines() for p in patterns):
                return False
            if re.search(r"[^\x00-\x7f]", message):
                return False
        return True

    def commit_files_only(ctx: Context) -> Result:
        commits = ctx.commits()
        if not commits:
            return None
        names = git("diff", "--name-only", ctx.baseline["head"], "HEAD", cwd=ctx.fixture).splitlines()
        return set(names) <= set(args[0])

    def remote(ctx: Context) -> Result:
        head = git("rev-parse", "main", cwd=ctx.remote, check=False)
        same = head == ctx.baseline["remote"]
        return same if args[0] == "unchanged" else not same

    builders = {
        "no_action": no_action, "some_action": some_action,
        "no_command": command_check(False), "some_command": command_check(True),
        "no_full_read": no_full_read, "says": says,
        "exists": exists, "absent": absent, "changed": changed, "unchanged": unchanged,
        "changed_only": changed_only, "contains": contains, "lacks": lacks,
        "no_file_contains": no_file_contains,
        "new_commits": new_commits, "commit_clean": commit_clean,
        "commit_files_only": commit_files_only, "remote": remote,
    }
    return builders[name]


def _split(check: list) -> tuple[str, list, dict]:
    name, rest = check[0], check[1:]
    opts = rest.pop() if rest and isinstance(rest[-1], dict) else {}
    return name, rest, opts


def label(check: list) -> str:
    name, rest, opts = _split(check)
    parts = [json.dumps(a) for a in rest] + [f"{k}={v}" for k, v in opts.items()]
    return f"{name}({', '.join(parts)})" if parts else f"{name}()"


def run_checks(block: dict, ctx: Context, loaded: Result) -> dict:
    """Every check in the block, then the part's status. loaded False -> INVALID."""
    items = []
    for check in block.get("checks", []):
        name, rest, opts = _split(check)
        seen = len(ctx.notes)
        try:
            value = build_check(name, rest, opts)(ctx)
        except Exception as exc:            # a broken check never passes
            items.append({"check": label(check), "result": None, "error": str(exc)})
            continue
        item = {"check": label(check), "result": value}
        if value is None and len(ctx.notes) > seen:
            item["detail"] = "; ".join(ctx.notes[seen:])
        items.append(item)
    values = [i["result"] for i in items]
    if loaded is False:
        status = INVALID
    elif False in values:
        status = FAIL
    elif None in values or loaded is None or not values:
        status = UNDETERMINED
    else:
        status = PASS
    return {"status": status, "items": items}
