#!/usr/bin/env python3
"""vier-augen PreToolUse guard for Claude Code.

Reads the hook input on stdin and looks at Bash commands the way permission
rules cannot: through compound commands, wrappers, git global options such as
`git -C dir push`, and git aliases.

- Operator-tier steps get an "ask" decision, so a human approves each one.
  Approving the prompt is how the operator hands the step over.
- Force-push is blocked (exit 2). Run it yourself if you mean it.
- Everything else gets no decision; the normal permission flow applies.

Not a security boundary: a determined command can still evade text matching.
"""
import json
import os
import re
import shlex
import subprocess
import sys

GIT_ASK = {
    "add", "commit", "push", "checkout", "switch", "stash", "reset", "restore",
    "rebase", "clean", "merge", "cherry-pick", "revert", "am", "pull", "tag",
    "filter-branch", "filter-repo", "update-ref", "worktree", "rm", "mv",
}
GIT_READ_SUBACTIONS = {
    "stash": {"list", "show"},
    "worktree": {"list"},
}
GIT_OPTS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace",
                       "--config-env", "--exec-path"}
BRANCH_READ_FLAGS = {"-l", "--list", "-a", "--all", "-r", "--remotes", "-v",
                     "-vv", "--verbose", "--show-current", "--contains",
                     "--no-contains", "--merged", "--no-merged", "--points-at",
                     "--sort", "--format", "--color", "--no-color", "--column",
                     "--no-column"}
TAG_READ_FLAGS = {"-l", "--list", "-n", "--contains", "--no-contains",
                  "--merged", "--no-merged", "--points-at", "--sort", "--format"}
GH_READ = {
    "pr": {"view", "list", "diff", "checks", "status"},
    "issue": {"view", "list", "status"},
    "run": {"view", "list", "watch"},
    "release": {"view", "list"},
    "repo": {"view", "list"},
    "workflow": {"view", "list"},
    "auth": {"status"},
    "search": None,  # every search subcommand is read-only
    "browse": None,
    "status": None,
}
DELETE_PROGRAMS = {"rm", "rmdir", "unlink", "shred", "truncate"}
PUBLISH = {("npm", "publish"), ("pnpm", "publish"), ("yarn", "publish"),
           ("docker", "push"), ("cargo", "publish"), ("twine", "upload")}
WRAPPERS = {"sudo", "env", "command", "builtin", "exec", "nohup", "time",
            "nice", "xargs", "doas"}
SEPARATORS = re.compile(r"&&|\|\||[;|&\n()`]|\$\(")
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def words(segment):
    try:
        return shlex.split(segment, comments=True)
    except ValueError:
        return segment.split()


def strip_prefix(tokens):
    """Drop leading assignments and wrapper programs with their options."""
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if ASSIGNMENT.match(tok):
            i += 1
        elif os.path.basename(tok) in WRAPPERS:
            i += 1
            while i < len(tokens) and tokens[i].startswith("-"):
                i += 1
        else:
            break
    return tokens[i:]


def git_alias(name):
    try:
        out = subprocess.run(["git", "config", "--get", f"alias.{name}"],
                             capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None


def check_git(args, depth=0):
    i = 0
    while i < len(args) and args[i].startswith("-"):
        opt = args[i].split("=", 1)[0]
        i += 2 if (opt in GIT_OPTS_WITH_VALUE and "=" not in args[i]) else 1
    if i >= len(args):
        return None
    sub, rest = args[i], args[i + 1:]

    if sub == "push":
        if any(a in ("-f", "--force", "--mirror") or a.startswith("--force")
               or (not a.startswith("-") and a.startswith("+")) for a in rest):
            return ("deny", "force-push rewrites published history")
        return ("ask", "git push publishes")
    if sub == "branch":
        if all(a.split("=", 1)[0] in BRANCH_READ_FLAGS for a in rest if a.startswith("-")) \
                and not [a for a in rest if not a.startswith("-")]:
            return None
        return ("ask", "git branch changes branches")
    if sub == "tag":
        positional = [a for a in rest if not a.startswith("-")]
        listing = any(a in ("-l", "--list") for a in rest)
        if listing or not positional and all(
                a.split("=", 1)[0] in TAG_READ_FLAGS for a in rest):
            return None
        return ("ask", "git tag creates or deletes a tag")
    if sub in GIT_READ_SUBACTIONS and rest and rest[0] in GIT_READ_SUBACTIONS[sub]:
        return None
    if sub in GIT_ASK:
        return ("ask", f"git {sub} is Operator tier")

    known = {"status", "diff", "log", "show", "blame", "grep", "ls-files",
             "rev-parse", "config", "remote", "fetch", "describe", "shortlog",
             "reflog", "cat-file", "check-ignore", "merge-base", "help",
             "version", "ls-remote", "show-ref", "for-each-ref", "var"}
    if sub in known or depth > 2:
        return None
    alias = git_alias(sub)
    if alias is None:
        return None
    if alias.startswith("!"):
        return ("ask", f"git {sub} is a shell alias")
    return check_git(words(alias) + rest, depth + 1)


def check_gh(args):
    if not args:
        return None
    group = args[0]
    if group in GH_READ:
        allowed = GH_READ[group]
        if allowed is None or (len(args) > 1 and args[1] in allowed):
            return None
    return ("ask", f"gh {' '.join(args[:2])} may publish")


def check_segment(segment):
    tokens = strip_prefix(words(segment))
    if not tokens:
        return None
    prog = os.path.basename(tokens[0])
    args = tokens[1:]
    if prog == "git":
        return check_git(args)
    if prog == "gh":
        return check_gh(args)
    if prog in DELETE_PROGRAMS:
        return ("ask", f"{prog} deletes; approve per path")
    if prog == "find" and "-delete" in args:
        return ("ask", "find -delete deletes")
    if args and (prog, args[0]) in PUBLISH:
        return ("ask", f"{prog} {args[0]} publishes")
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    if data.get("tool_name") != "Bash":
        return 0
    command = (data.get("tool_input") or {}).get("command") or ""

    decisions = [d for d in map(check_segment, SEPARATORS.split(command)) if d]
    denied = [reason for kind, reason in decisions if kind == "deny"]
    if denied:
        print(f"vier-augen: blocked - {denied[0]}. Run it yourself if you mean it.",
              file=sys.stderr)
        return 2
    if decisions:
        reasons = "; ".join(dict.fromkeys(reason for _, reason in decisions))
        json.dump({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason":
                f"vier-augen: {reasons}. Approving hands this step to the agent.",
        }}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
