# 0003 - The harness is agent-neutral; an agent enters through a profile

- Status: Accepted
- Date: 2026-09-20 20:19 +02:00

## Context

Taken while the checks were implemented in September 2026, and recorded here
afterwards.

The scenarios say nothing about any particular agent: they are messages and
expectations. What differs between agents is how a session is started, where
the transcript lands and what it looks like, and which tool names write to
disk. Putting that knowledge wherever it was first needed would have spread one
agent's vocabulary through the whole harness.

Keeping a separate harness per agent was considered and rejected. Copies drift,
so a check would come to mean slightly different things for different agents,
and comparing a result across them would prove nothing. It would also end the
single entry point of ADR 0002.

## Decision

`tests/vier-augen/harness.py` is agent-neutral. It holds the transcript model,
the classification of a command, the realisation of every check named by a
scenario block, and the two rules that make a result trustworthy: a check that
cannot be settled returns undetermined rather than passing, and a session the
skill's text never reached is invalid rather than failing.

Everything specific to one agent lives in `tests/vier-augen/profiles/`: the
tool names that write or only read, how to launch a headless turn, how to find
and parse a transcript, and the preflight that refuses to measure a session
where an adapter or a personal instruction file would mask the text.

Supporting a second agent means adding a profile beside the first, and an
adapter under the skill's `adapters/`. It does not mean touching the harness.

One dependency crosses that line today: the command classifier imports the
Claude Code adapter's `guard.py`, deliberately, so that the test and the guard
agree on what a command does. The code it uses is plain shell and git parsing,
but its address is not neutral and it is to be moved to a neutral module.

## Consequences

A check means the same thing whatever agent produced the transcript, so results
can be compared. A new agent is an additive change with a bounded surface.

The cost is indirection - the harness asks a profile for things it could have
hardcoded - and one known exception that has to be carried in the documentation
until it is resolved.
