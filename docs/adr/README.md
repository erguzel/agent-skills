# Architecture decisions

This directory records decisions about how this repository is built and
tested: the choices a later reader would otherwise have to reconstruct from
the code, and would be free to reverse without knowing what it cost.

A record is written when a decision is made, not afterwards. It is short.
`AGENTS.md` says when one is owed; this file says how to write it.

## Where a decision belongs

Three documents hold reasoning in this repository. A reason is written in one
of them and referenced from the others, never copied.

| The reason concerns | It belongs in |
| --- | --- |
| A rule inside a skill - why `SKILL.md` says what it says | that skill's `references/rationale.md` |
| How this repository is built, tested or released | an ADR here |
| What a contributor must do while working here | `AGENTS.md` |

An ADR explains why a structure is the way it is. `AGENTS.md` states what to
do. If a new rule needs both, write the ADR and keep the `AGENTS.md` line to
one imperative sentence.

## Format

One file per decision, `NNNN-short-slug.md`, numbered in the order decisions
were taken. Sections, in this order:

```markdown
# NNNN - Title, as a decision

- Status: Accepted
- Date: 2026-09-20 20:15 +02:00

## Context

What was true when the decision was taken, and what forced a choice.

## Decision

What was decided, in the present tense.

## Consequences

What this makes easy, what it makes hard, and what it rules out.
```

Status is `Accepted`, or `Superseded by NNNN`.

`Date` is when the record was written, to the minute, with the offset spelled
out. When the decision itself was taken earlier - a record written after the
fact - the first sentence of `Context` says when, because the file must not
claim a precision it does not have.

## Changing a decision

Do not edit an accepted ADR to say something else, and do not delete it. Write
a new one, and set the old one's status to `Superseded by NNNN`. The point of
this directory is that a reader can see what was believed at the time, not only
what is believed now.
