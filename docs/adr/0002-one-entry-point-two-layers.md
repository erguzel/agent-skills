# 0002 - One entry point, and the two test layers never run in one command

- Status: Accepted
- Date: 2026-09-20 20:19 +02:00

## Context

Taken over the runner work in September 2026, and recorded here afterwards.

The skill protects in layers. Its text steers an agent; git hooks and an agent
adapter enforce a few of the same rules mechanically. Those layers have to be
tested with opposite setups, and each one hides the other: with the hooks
installed, a commit carrying assistant attribution is refused whether or not
the agent's instructions worked, so a text rule that failed looks like it held.

Running them apart by hand was documented and, predictably, only half done.

## Decision

`tests/vier-augen/run.py` is the only entry point.

`run.py verify` measures the mechanical layer: it builds a throwaway
repository, installs the hooks there and hands each hook and the adapter's
guard the input it is meant to stop. Hooks on, no agent, deterministic, free,
and it runs in CI on every pull request.

`run.py <scenarios>` measures the instruction layer against a fixture the
hooks are switched off in, driving a live agent.

The two are refused in one command. The messages the hooks and the guard print
are an interface: `verify` matches them, so changing one deliberately means
changing its check in the same commit.

## Consequences

Whoever clones the repository has one command to learn and cannot silently
measure a masked layer. CI can run the mechanical half on every change, which
is where most regressions would otherwise appear unnoticed.

The cost is that the runner has two quite different modes behind one name, and
a rule to keep them apart that has to be stated in its help, its documentation
and its tests.
