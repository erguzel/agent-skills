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
npx skills add erguzel/agent-skills --skill vier-augen      # this project
npx skills add erguzel/agent-skills --skill vier-augen -g   # every project
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

#### Verify

The hooks fail closed, so a broken install stays quiet until something slips
through. These checks use real input: each one stages or pushes what a hook is
meant to stop. Run them in a throwaway repository, never in your own.

From a clone of the skill's own repository, one command runs all of them in a
throwaway repository it builds and removes itself:

```bash
python3 tests/vier-augen/run.py verify
```

It matches the messages the hooks print, so those messages are an interface:
change them deliberately, and change the checks with them.

```bash
git init /tmp/va-check && cd /tmp/va-check
git config user.email you@example.com && git config user.name You
sh <path-to-this-skill>/hooks/install.sh
echo seed > a.txt && git add a.txt && git commit -m "init: seed"
BR=$(git branch --show-current)      # the default branch name varies
```

1. **Installed.**

   ```bash
   ls .git/hooks/commit-msg .git/hooks/pre-commit .git/hooks/pre-push
   ```

   Three files. Missing: the installer ran outside the repository, or
   `core.hooksPath` is set and it printed lines for you to add by hand.

2. **Attribution in the message.**

   ```bash
   echo x >> a.txt && git add a.txt
   git commit -m "test: trailer" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
   ```

   Refused: `assistant attribution found in the message`. If it commits,
   `commit-msg` is not wired, or `hooks/attribution/` is not where it expects.

3. **Agent identity.**

   ```bash
   GIT_AUTHOR_NAME=Claude GIT_AUTHOR_EMAIL=noreply@anthropic.com git commit -m "test: identity"
   ```

   Refused: `coding-agent identity in GIT_AUTHOR_IDENT`.

4. **Staged secret.**

   ```bash
   git reset && printf 'key = %s%s\n' AKIA ABCDEFGHIJKLMNOP > secret.txt
   git add secret.txt && git commit -m "test: secret"
   ```

   Refused: `possible AWS access key at secret.txt:1`. The value is never
   printed - if you see it in the output, that is a bug worth reporting. (The
   two example lines here assemble their bait at run time, so that this
   document does not trip the hook it describes.)

5. **Personal path.**

   ```bash
   git reset && rm secret.txt
   printf 'path = /%s/someone/Projects/thing\n' Users > pathy.txt && git add pathy.txt
   git commit -m "test: path"
   ```

   Refused: `possible personal home path at pathy.txt:1`.

6. **Force-push.** No network needed - a local bare repository is a remote.

   ```bash
   git reset && rm pathy.txt
   git init --bare /tmp/va-remote.git && git remote add origin /tmp/va-remote.git
   git push origin "$BR"
   git commit --amend --no-verify -m "init: seed (amended)"
   git push --force origin "$BR"
   ```

   The ordinary push succeeds; the last command is refused with `would rewrite
   history on origin`.

Clean up with `rm -rf /tmp/va-check /tmp/va-remote.git`.

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
  force-push. It needs `python3`, and it needs the skill folder around it: the
  decision itself is made by `lib/tiers.py`, shared with the behaviour tests.
  Copied out on its own, the guard asks for every command and says why on
  stderr, rather than letting anything through.

Merge the template into one of your settings files: `.claude/settings.json`
(shared with the project), `.claude/settings.local.json` (yours) or
`~/.claude/settings.json` (every project). Merge the `permissions` and `hooks`
keys by hand rather than copying over an existing file. The hook command assumes
a project install; for a global install, point it at
`~/.claude/skills/vier-augen/adapters/claude-code/guard.py`.

Answering the prompt is how you hand a step to the agent: your "yes" is the
handover. Force-push is refused outright - run it yourself when you mean it.

#### Verify

The first three checks need no agent and cost nothing: they hand the guard a
tool call on stdin and read its answer. Adjust the path for a global install.
From a clone of the skill's own repository, `python3 tests/vier-augen/run.py
verify` runs them together with the Level 1 checks.

```bash
G=.claude/skills/vier-augen/adapters/claude-code/guard.py
probe() { echo "$1" | python3 "$G"; echo "exit=$?"; }
probe '{"tool_name":"Bash","tool_input":{"command":"git push --force origin main"}}'
probe '{"tool_name":"Bash","tool_input":{"command":"git status"}}'
probe '{"tool_name":"Bash","tool_input":{"command":"git -C . add probe.txt"}}'
```

In order: `blocked - force-push rewrites published history` with `exit=2`; no
output with `exit=0`; a `"permissionDecision": "ask"` object with `exit=0`. The
third is what the permission rules alone would miss, since `git -C <dir> add`
does not match `Bash(git add *)`. Identical answers to all three mean the guard
is not deciding - check that `python3` is there and that the path resolves.

The last three need a live agent, so they cost tokens. In a throwaway
repository, with the template merged and the session restarted:

- Ask the agent to stage a file with `git add`. A prompt appears before the
  command runs. Do not tick "don't ask again" - it blinds the next check.
- Ask it to run `git -C . add <file>`. A prompt appears again; this one is the
  guard's.
- Hand a force-push over by name. The runtime refuses it outright.

The last one rarely gets that far: the skill's text stops the agent first, and
an agent that declines on its own has not exercised the rule. The stdin probe
above is what verifies it.

Things to know:

- Claude Code's `bypassPermissions` mode skips permission prompts, so the `ask`
  rules do not protect you there. The guard's force-push block still applies.
- Rules and guard match command text. They cover the forms an agent usually
  writes, not every possible form, and are not a security boundary.
- Other agents have their own permission systems. An adapter for one lives in
  `adapters/<agent>/` beside this one, and the behaviour tests reach it through
  a profile of the same name; until an agent has both, levels 0, 1 and 3 apply
  to it.

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

**What it carries over.** The standing instructions you gave during the
session - how to work, talk and decide - each in one line and in its latest
form, with anything the agent only inferred marked as such. One-off requests
stay behind, and so do handovers: a checkpoint records what you decided and
grants nothing in the next session.

**Picking it up.** A new session reads the checkpoint only when you tell it to -
for example, "continue from `.ai/eigenkontext.md`". It then lists the carried
instructions and asks which still apply - all, some or none - before it does
anything else. Until then the checkpoint is a file like any other.

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
- **The model underneath.** Level 0 is text, so it assumes a model that can
  carry a four-thousand-token agreement across a whole session and act on it at
  the right moment. A smaller or weaker model will drop parts of it, quietly.
  Nothing in the skill can detect that. Where you cannot rely on the model,
  lean on levels 1 and 2, which do not depend on it at all.
- **Agents without a print mode.** The behaviour tests drive the agent headless.
  An agent that has no such mode is still testable, with
  `run.py --driver manual`, but then the steps are typed by a human: for those
  agents "no manual work" is not true.

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
| [`lib/tiers.py`](lib/tiers.py) | Which tier a shell command falls into. The one classifier, read by every adapter's guard and by the behaviour tests. |
| [`ci/vier-augen.yml`](ci/vier-augen.yml) | Pull request check for your own repository. |
| [`references/rationale.md`](references/rationale.md) | Why the sharper rules are shaped the way they are. Read on demand. |

## Contributing

This is a working agreement, not a style guide. A rule earns its place by
changing what the agent does at a decision point. If a proposed rule would not
alter any concrete action, it belongs in `references/rationale.md` or nowhere.
See [CONTRIBUTING.md](../../CONTRIBUTING.md) for how changes are judged.
