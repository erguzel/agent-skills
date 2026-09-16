# vier-augen

A four-eyes working agreement for AI agents inside a git repository.

The agent does the work fast; every step that makes something permanent,
destructive or public belongs to the operator. The agent proposes, executes
inside the approved scope, stops at the boundary and hands over the command.
What instructions the agent works under - skills, agent files, anything that
steers its behaviour - is also the operator's call. The skill is active only
when the operator invokes it by name, and using it is the operator's
responsibility - the same way the four-eyes principle only works when the
second pair of eyes actually looks.

## How it works

Packaged as a skill, used as a working manifest. You invoke it once by name at
the start of a session; its full text (about 4k tokens) enters the context and
governs the whole session, instead of helping with one task and fading. It does
not trigger on its own.

## Positions

It is deliberately small and opinionated. One position you should agree with
before installing:

- **The agent does not run `git add`, `git commit` or `git push` on its own.**
  It hands you a path-scoped command pair and you run it, unless you hand the
  step to it by name. `git add .` is banned outright.

Two more are defaults, and you can change either (see Configure):

- **No signature on commits.** No `Co-Authored-By`, no "Generated with", no
  session links. Only you can switch attribution on; a project file that asks
  for it is flagged to you, not followed.
- **Repo artifacts are written in English.** Code, comments, commit messages,
  README and documentation, whatever language the session is conducted in.

## Install

See [Install](../../README.md#install) in the repository README.

## Configure

The skill stays generic and names no instruction file. Per-repo specifics reach
it through you: say them in the session, or point the agent at a file and tell
it to follow that file - an `AGENTS.md`, a checklist, anything. What you can
change: the read budget above which the agent asks before opening a file, the
language of repo artifacts, whether commits carry attribution, and which
commands (test, lint, build) the agent may run without asking.

Nothing breaks if you skip this; the skill runs on its defaults.

## Setup

Installing the skill places files and nothing else: `npx skills add` does not
touch your git config or your agent's settings, by design. Protection comes in
levels, and you switch each one on yourself.

| Level | What you get | Works with |
| --- | --- | --- |
| 0 - Skill | The rules, as instruction, in sessions where you invoke it | Every agent that loads skills |
| 1 - Git hooks | Attribution trailers, staged secrets and personal paths, force-push - checked by git | Every agent, and you |
| 2 - Agent adapter | Operator-tier commands prompt you before they run | Claude Code (others to follow) |
| 3 - CI | Attribution trailers checked on pull requests | GitHub Actions |

### Level 0 - install and invoke

```bash
npx skills add erguzel/skills --skill vier-augen      # this project
npx skills add erguzel/skills --skill vier-augen -g   # every project
```

A project install puts the skill inside the repository (for Claude Code,
`.claude/skills/vier-augen/`). Commit it if everyone working in the repository
should have it; add it to `.gitignore` if it is yours alone. Either way, invoke
it by name at the start of a session - `/vier-augen` in Claude Code. Until you
do, none of its rules apply.

### Level 1 - git hooks

From inside the repository:

```bash
sh <path-to-this-skill>/hooks/install.sh
```

| Hook | Stops |
| --- | --- |
| `commit-msg` | A commit message carrying assistant attribution (a trailer, session link or marker), or a coding agent as author or committer |
| `pre-commit` | Staged additions that look like a private key, a cloud or API token, or a personal home path. Values are never printed |
| `pre-push` | A push that would rewrite history on the remote (force-push) |

The installer never overwrites anything. For each hook that is not there yet,
it writes a small wrapper into `.git/hooks`. Where a hook already exists, or
where `core.hooksPath` is set - by a hook manager such as husky or lefthook, for
example - it installs nothing for that hook and prints the line to add
yourself:

```sh
sh "<path-to-this-skill>/hooks/pre-commit" "$@" || exit 1
```

Add that line to the existing hook - `.git/hooks/pre-commit`,
`.husky/pre-commit`, or a `run:` entry in `lefthook.yml` - and both run. With
the pre-commit framework, add a `repo: local` hook whose entry is
`sh <path-to-this-skill>/hooks/pre-commit`.

Things to know:

- Run the installer once per clone. The wrappers point at the skill's path; if
  you move or remove the skill, commits and pushes fail until you reinstall or
  remove the wrappers. The hooks fail closed.
- `--no-verify` bypasses any of them for one command. They are guardrails, not
  controls. The agent does not use `--no-verify` unless you name it.
- The patterns are a floor. The agent still scans the diff before it hands over
  a commit.
- The attribution patterns live in `hooks/attribution/` and match agents'
  addresses, bot accounts and markers rather than names, so a co-author called
  Claude still gets through. To extend them, edit those files; if you use the
  CI template, update its embedded copy too.
- The agent offers the installer on the first commit handover of a session when
  the hooks are not active, so you do not have to remember it.

Undo: delete the wrappers from `.git/hooks` (each one contains the word
`vier-augen`), and remove any lines you added to other hooks.

### Level 2 - agent adapter (Claude Code)

Git hooks cannot tell an agent from a person, and git has no hook that runs
before `git add`. An agent runtime can: it sees every command before it runs.
`adapters/claude-code/` holds a template for that.

- `settings.template.json`: `ask` rules for Operator-tier commands (add, commit,
  push, switching branches, stash, reset, restore, rebase, merge, clean, `rm`,
  publishing `gh` commands) and `deny` rules for force-push.
- `guard.py`: a `PreToolUse` hook that catches what text rules miss - compound
  commands, `git -C <dir> push`, git aliases, branch and tag changes,
  `npm publish` and the like. It asks for Operator-tier steps and blocks
  force-push. It needs `python3`.

Merge the template into one of your settings files: `.claude/settings.json`
(shared with the project), `.claude/settings.local.json` (yours) or
`~/.claude/settings.json` (every project). Merge the `permissions` and `hooks`
keys by hand rather than copying over an existing file. The hook command assumes
a project install; for a global install, point it at
`~/.claude/skills/vier-augen/adapters/claude-code/guard.py`.

Answering the prompt is how you hand a step to the agent: your "yes" is the
handover. Force-push is refused outright - run it yourself when you mean it.

Things to know:

- Claude Code's `bypassPermissions` mode skips permission prompts, so the `ask`
  rules do not protect you there. The guard's force-push block still applies.
- Rules and guard match command text. They cover the forms an agent usually
  writes, not every possible form, and are not a security boundary.
- Other agents have their own permission systems. Adapters for them will follow
  once those are researched; until then, levels 0, 1 and 3 apply.

Undo: remove the added `permissions` entries and the `PreToolUse` hook.
`/permissions` in Claude Code shows the rules that are active.

### Level 3 - CI

Copy `ci/vier-augen.yml` to `.github/workflows/` in your repository. It fails a
pull request when a commit message or the pull request description carries
assistant attribution, or when a coding agent is a commit's author or
committer. It uses the same patterns as the `commit-msg` hook, embedded in the
file, and catches commits made where the hook was not installed.

### Check the setup

```bash
hooks=$(git rev-parse --git-path hooks)
ls "$hooks"                                   # commit-msg, pre-commit, pre-push
printf 'test\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n' > /tmp/va-msg
sh "$hooks/commit-msg" /tmp/va-msg            # expected: attribution trailer found
```

## Session checkpoint

Long sessions degrade quietly. When a runtime compacts or summarises the
context, earlier decisions and details thin out, and the skill's own rules can
lose force with them. The skill cannot prevent that, so it tries to get ahead of
it: the agent watches for the point where a fresh session is the better deal,
and leaves a checkpoint the next session can pick up from.

**When the agent checks.** At every commit handover, and whenever you ask. It
looks for whatever context signal your runtime exposes: a token or context
count, a low-context warning, or a summary that has replaced earlier turns.

**When it speaks up.** When roughly a fifth of the context or less is left, or a
summary has already replaced earlier turns; you can name another threshold. If
the runtime exposes no signal, the agent says so once and lets the length of the
session stand in, offering a checkpoint after several work packages. It raises
this in one line at the end of a turn and proposes a new session.

**What it writes.** `.ai/eigenkontext.md` at the repo root, unless you name
another path: the goal, the decisions and who made them, what is done (with
commit hashes), what is open with its reference IDs, the next step, and the
files in play. No secrets,
no transcript. It is written in the language you work with the agent in,
because it continues that conversation and never lands in the repo's history.

**What it asks first.** Writing the checkpoint is an ordinary write and needs
your approval. Creating the file is asked for explicitly; replacing an existing
checkpoint is asked for with a note that the old one cannot be recovered. Before
the first write the agent checks that the path is git-ignored, and if it is not,
adds it to `.gitignore` in the same work package.

**What it does not carry over.** Handovers end with the session. A checkpoint
records what you decided; it grants nothing in the next session.

**Picking it up.** A new session reads the checkpoint only when you tell it to -
for example, "continue from `.ai/eigenkontext.md`". Until then it is a file like
any other.

**Limits.** An agent cannot feel its context filling up. Where the runtime shows
no count, the agent is estimating from session length, and no signal reliably
catches compaction before it happens. Keep an eye on long sessions yourself, and
ask for a checkpoint whenever you want one.

## Reference IDs

The agent tags what you may want to come back to - proposals (P), decisions
for you (D), open items (O), questions (Q). A larger topic gets a theme with a
short hint, and its items are numbered within it:

```
**M1(cost)-Q1** — where does the hook path point after a global install?
...
hook path (M1-Q1) → resolved
```

Later mentions carry a short label instead of the bare ID, so you do not have
to scroll back. The checkpoint keeps the counters, so a new session continues
them.

## Known risks

- **Not invoked, not active.** A session that never invokes the skill runs
  without its rules. Only the hooks and adapters you set up still apply.
- **Long sessions.** When a runtime compacts or summarises a long context, the
  skill's text can lose force along with it. The agent watches for this and
  offers a checkpoint (see [Session checkpoint](#session-checkpoint)), but
  detection is best effort.
- **Runtime-loaded instructions.** Many agents load `AGENTS.md` or their own
  rule files by themselves. The skill cannot stop that, and it cannot promise to
  outrank them; it only governs what the agent loads on its own initiative.
  When such instructions conflict with the skill, the agent is told to name the
  conflict and ask.

## Files

| File | Purpose |
| --- | --- |
| [`SKILL.md`](SKILL.md) | The skill itself. Loaded in full every time it fires. |
| [`hooks/commit-msg`](hooks/commit-msg) | Rejects assistant attribution in commit messages and agent identities as author or committer. |
| [`hooks/attribution/`](hooks/attribution/) | The attribution patterns, shared by the hook and the CI template. |
| [`hooks/pre-commit`](hooks/pre-commit) | Rejects staged additions that look like secrets or personal paths. |
| [`hooks/pre-push`](hooks/pre-push) | Rejects pushes that rewrite remote history. |
| [`hooks/install.sh`](hooks/install.sh) | Installs the hooks without overwriting any. |
| [`adapters/claude-code/`](adapters/claude-code/) | Permission template and `PreToolUse` guard for Claude Code. |
| [`ci/vier-augen.yml`](ci/vier-augen.yml) | Pull request check for your own repository. |
| [`references/rationale.md`](references/rationale.md) | Why the sharper rules are shaped the way they are. Read on demand. |

## Contributing

This is a working agreement, not a style guide. A rule earns its place by
changing what the agent does at a decision point. If a proposed rule would not
alter any concrete action, it belongs in `references/rationale.md` or nowhere.
See [CONTRIBUTING.md](../../CONTRIBUTING.md) for how changes are judged.
