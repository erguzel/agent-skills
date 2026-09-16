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

## Known risks

- **Not invoked, not active.** A session that never invokes the skill runs
  without its rules. Only installed hooks still apply.
- **Long sessions.** When a runtime compacts or summarises a long context, the
  skill's text can lose force along with it. No reliable mitigation is settled
  yet.
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
