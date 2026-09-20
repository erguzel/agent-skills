# 0001 - A scenario lives in one file, prose and machine-readable side by side

- Status: Accepted
- Date: 2026-09-20 20:19 +02:00

## Context

Taken while the behaviour scenarios were first written, in September 2026, and
recorded here afterwards.

The scenarios have two readers. A person decides whether a scenario is worth
its cost and judges the transcript against it; a program builds the fixture,
sends the steps and runs the checks that need no judgment. An earlier attempt
gave each scenario a Python module, which the program read well and nobody else
did: the situation being tested disappeared into constructor arguments, and the
prose describing it drifted into a separate document that went stale.

## Decision

A scenario is one section of `tests/vier-augen/scenarios.md`: prose first -
set, what it covers, purpose, notes - then one fenced JSON block carrying
`setup`, `steps`, `expected`, `fail_if`, `checks` and the optional
`continues`, `fixture` and `mode`.

Nothing is stated twice. The identifier, the set and the covered sections are
read from the prose, never repeated in the block. `tools/validate_scenarios.py`
enforces the shape, the numbering, the ordering of the sets and the check
vocabulary, and runs in CI.

## Consequences

A scenario can be read and reviewed as text, which is what decides whether it
earns its place. The runner parses the same file, so a scenario cannot be
runnable and stale at once.

The cost is a parser for a document format instead of an import, and a
validator to keep the format honest. Both are cheaper than two sources that
disagree.
