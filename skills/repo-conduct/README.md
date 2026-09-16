# repo-conduct

A working agreement for AI agents inside a repository.

It answers one question over and over: **when does the agent act, and when does
it stop and ask?** Concretely, it sets out how a session opens, when approval is
required before a write, how a claim gets labelled with the evidence behind it,
when documentation is expected to move with the code, and how commits are handed
back to the human instead of run by the agent.

It is deliberately small and opinionated. One position you should agree with
before installing:

- **The agent never runs `git add`, `git commit` or `git push`.** It hands you a
  path-scoped command pair and you run it. `git add .` is banned outright.

Two more are strong defaults rather than rules, and your `AGENTS.md` can change
either:

- **No signature on commits.** No `Co-Authored-By`, no "Generated with", no
  session links. A project that asks for attribution in writing gets it.
- **Repo artifacts are written in English.** Code, comments, commit messages,
  README and documentation, whatever language the session is conducted in.

## Install

See [Install](../../README.md#install) in the repository README.

## Configure

The skill stays generic; per-repo specifics belong in your own `AGENTS.md`.
Whatever that file designates is authoritative and overrides the skill's
defaults: reference files and directories, the project's commands, and the read
budget above which the agent asks before opening a file, the language of repo
artifacts, and whether commits carry attribution.

Nothing breaks if you skip this. With no `AGENTS.md`, the skill reports the
missing file in one line and carries on with its defaults.

## Enforce it

`SKILL.md` is instruction, so an agent can drift from it. The shipped hook does
not. From the repo where the skill is installed:

```bash
git config core.hooksPath <path-to-this-skill>/hooks
```

It rejects any commit message carrying an assistant attribution trailer, and
nothing else - no language check, no message-format check. Set it once per
clone; `git commit --no-verify` bypasses it for a single commit, so treat it as
a guardrail rather than a control. The skill tells the agent to offer this
command on the first commit handover of a session when the config is unset, so
you do not have to remember it.

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
