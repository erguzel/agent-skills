# 0005 - A change owes the scenarios it touches; a release owes the whole Core set

- Status: Accepted
- Date: 2026-09-20 20:19 +02:00

## Context

Taken in September 2026 while the runner's selection was designed, and recorded
here afterwards.

The rule used to be that any change to a rule in `SKILL.md` needed the
scenarios covering it, run by hand in a live agent. Every scenario costs tokens
and attention, so the rule was never once carried out: it asked for a payment
nobody could make, and a rule that is always skipped protects nothing.

## Decision

`run.py --affected <base>` names the scenarios a change owes. It maps the
sections of `SKILL.md` the diff touches onto the `Covers` line of each
scenario; a change reaching the frontmatter or the text above the first heading
affects every scenario. When it names none, none are owed.

A release is the exception and owes the whole Core set, plus any Comfort
scenario covering what the release touches.

The subset is only as good as the `Covers` lines it reads. The runner warns
about a scenario naming a section that does not exist; it cannot detect one
that names too few.

## Consequences

The obligation is now small enough to meet, and mechanical enough to check
before opening a pull request.

The cost is a new way to be wrong: a scenario with a careless `Covers` line
drops out of the selection silently. Writing that line is part of writing a
scenario, and a release still runs everything.
