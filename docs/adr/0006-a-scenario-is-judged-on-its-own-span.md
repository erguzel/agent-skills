# 0006 - A scenario is judged on its own span, not on the finished session

- Status: Accepted
- Date: 2026-09-20 21:45 +02:00

## Context

Taken while the runner was built in September 2026, and recorded here
afterwards.

Scenarios can be chained: one names another it continues, and the chain shares
a single agent conversation and a single fixture, because what the earlier
scenario established is what the later one is measured against. That leaves a
question the scenario file does not answer: over which part of the conversation
is a scenario's `checks` block read.

Scoring the whole session once, at the end, is the obvious implementation and
it was tried. It is wrong in both directions. A later scenario's commands
appear in the transcript an earlier scenario is judged against, so a rule the
agent kept in its own turn can be reported as broken. The reverse is worse: a
scenario that started a chain can be reported as held because a later turn
tidied up after it, which is the failure the chain exists to expose.

## Decision

A scenario is judged over its own span of the conversation, and nothing later
than it.

Under the driver the judgment happens the moment a scenario's last step is
answered, before the next scenario's first message is sent: the transcript
carries nothing from what follows, and the fixture stands as that scenario left
it.

The manual path judges a session after it is over, so it bounds each scenario
above by the next scenario's first message and reads only that window.

A chain shares one conversation and one fixture. It does not share a verdict.

## Consequences

A scenario's result means the same thing whether it ran alone or in the middle
of a chain, so the two can be compared, and a defect cannot be hidden by a
later turn that repairs the tree.

The driver pays for this by reading the transcript between every scenario
rather than once at the end.

The manual path can bound the transcript this way but not the fixture: the
files are only ever seen as the whole session left them, so a state check in a
chained scenario is weaker there than under the driver. `--driver manual` is
therefore for an agent the runner cannot drive, not a substitute for it.
