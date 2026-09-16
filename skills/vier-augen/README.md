# vier-augen

A four-eyes working agreement for AI agents inside a git repository.

The agent does the work fast; every step that makes something permanent,
destructive or public belongs to the operator. The agent proposes, executes
inside the approved scope, stops at the boundary and hands over the command.
What instructions the agent works under - skills, agent files, anything that
steers its behaviour - is also the operator's call. The skill is active only
when the operator invokes it by name, and using it is
the operator's responsibility - the same way the four-eyes principle only works
when the second pair of eyes actually looks.

It is deliberately small and opinionated. One position you should agree with
before installing:

- **The agent does not run `git add`, `git commit` or `git push` on its own.**
  It hands you a path-scoped command pair and you run it, unless you hand the
  step to it by name. `git add .` is banned outright.

Two more are defaults, and you can change either (see Configure):

- **No signature on commits.** No `Co-Authored-By`, no "Generated with", no
  session links. A project that asks for attribution in writing gets it.
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

## Enforce it

`SKILL.md` is instruction, so an agent can drift from it, and it does nothing in
a session where it was never invoked. The shipped hook does not drift and does
not need the skill to be loaded. For stricter protection, install it.
`npx skills add` only places files; it does not touch your git config, by
design. From the repo where the skill is installed:

```bash
git config core.hooksPath <path-to-this-skill>/hooks
```

It rejects any commit message carrying an assistant attribution trailer, and
nothing else - no language check, no message-format check. Set it once per
clone; `git commit --no-verify` bypasses it for a single commit, so treat it as
a guardrail rather than a control. The skill tells the agent to offer this
command on the first commit handover of a session when the config is unset, so
you do not have to remember it.

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
commit hashes), what is open, the next step, and the files in play. No secrets,
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

## Known risks

- **Not invoked, not active.** A session that never invokes the skill runs
  without its rules. Only installed hooks still apply.
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
| [`hooks/commit-msg`](hooks/commit-msg) | Opt-in `commit-msg` hook that enforces the no-signature rule. |
| [`references/rationale.md`](references/rationale.md) | Why the sharper rules are shaped the way they are. Read on demand. |

## Contributing

This is a working agreement, not a style guide. A rule earns its place by
changing what the agent does at a decision point. If a proposed rule would not
alter any concrete action, it belongs in `references/rationale.md` or nowhere.
