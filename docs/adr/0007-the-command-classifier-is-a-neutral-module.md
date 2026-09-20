# 0007 - The command classifier is a neutral module; an adapter's guard wraps it

- Status: Accepted
- Date: 2026-09-20 23:18 +02:00

## Context

ADR 0003 made the harness agent-neutral and named one dependency that crossed
the line: the harness imported its command classifier from the Claude Code
adapter's `guard.py`, so that the test and the guard would agree on what a
command does. It said the classifier was to move into a neutral module. This
record carries that out; ADR 0003 stands.

Where the module can live is constrained by how the skill is shipped. The
skill is installed by copying its folder, and the guard runs from inside that
copy with nothing else present, so a module the guard needs cannot live under
`tests/`. The test side may depend on the skill; the skill may not depend on
the test side. The module therefore lives inside the skill.

The classifier also spoke the runtime's language. It answered `ask` or `deny`,
which are Claude Code's permission decisions, and the harness read `deny` to
mean a force-push. A second adapter would have had to translate from one
runtime's vocabulary to another's.

## Decision

The classifier is `skills/vier-augen/lib/tiers.py`. It names no agent and
speaks the skill's own words: a command is Operator tier, or it rewrites
published history, or it is neither. The reason it gives is prose.

An adapter's guard is a wrapper over it. It reads the runtime's hook input,
asks the module, and translates the answer into that runtime's decisions -
for Claude Code, Operator tier becomes `ask` and a rewrite becomes `deny`.
The harness reads the same module and translates the same answer into the
kinds its checks use.

A guard that cannot find the module does not fall open. It says so on standard
error and asks for every command until the module is back. `run.py verify`
checks this by running a copy of the guard on its own.

The guard is no longer a file that can be copied by itself; it needs the skill
folder around it. The skill's README says so.

## Consequences

A second adapter shares the classifier instead of copying it or importing
another agent's, and a classification fixed once is fixed for the guard, the
harness and every adapter. The harness has one dependency fewer on any
agent's files.

The cost is one more file in the skill, an import in the guard that has to
resolve wherever the runtime starts it, and a failure mode that had to be
designed rather than left to chance.
