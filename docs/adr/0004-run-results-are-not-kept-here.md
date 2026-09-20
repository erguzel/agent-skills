# 0004 - Run results are not kept in this repository

- Status: Accepted
- Date: 2026-09-20 20:19 +02:00

## Context

Taken early in the behaviour-test work and reaffirmed when the runner was
built, in September 2026; recorded here afterwards.

A scenario result is only meaningful together with the agent, the model version
and the operating system that produced it, and it expires as soon as any of
them moves. Committed results would read as the current state of the skill
while describing a session nobody can reproduce, and a passing file in the tree
is exactly the kind of evidence people stop questioning.

## Decision

The runner writes its results outside the repository: `VA_RESULTS`, by default
`/tmp/va-results`. `run.py --report` reads them from there. Nothing under
`tests/` records an outcome, and `/.ai/` - where a session keeps its logs and
notes - is ignored in full.

Evidence of a run belongs in the pull request that relies on it, stated with
the agent, the model version and the operating system.

## Consequences

The repository carries what is reproducible - the scenarios, the checks, the
runner - and not the snapshots. A reader cannot mistake an old pass for a
current guarantee.

The cost is that results are local and disappear with the machine, so a claim
about a run has to be written down deliberately, in the pull request, by the
person who made it.
