# Rationale

Why the sharper rules in `SKILL.md` are shaped the way they are. This file is not
loaded unless a rule looks wrong for the situation, or the operator asks for a
justification.

## Why only one rule is absolute

Most of this skill is a default that `AGENTS.md` or the operator can override.
One rule is not: the operator runs `git add`, `git commit` and `git push`. The
line between the two is irreversible harm. A commit is the last point at which a
human can look at something before it becomes permanent and public, and nothing
undoes a push into someone else's clone. Everything else here - the language of
repo artifacts, attribution trailers, the read budget - is a policy preference
whose worst case is a file written the wrong way, fixed by the next commit.

Absolutes spend the installer's goodwill, so they are worth spending only where
being wrong cannot be undone. Where an operator wants a default enforced as
hard as a rule, `hooks/commit-msg` is there to install; opting in is the
configuration.

## Why side effect is the sorting key

Every "should I ask?" question collapses into one test: can the operator undo
this cheaply? Reading cannot hurt them. Writing, executing and filling the
context window can. Sorting by side effect rather than by topic means the rule
generalises to situations this file never anticipated.

## Why agent files are reported but not edited

`AGENTS.md` is the operator's promise to everyone else who works in the repo,
human or agent. An agent that edits it is rewriting a contract it is also a
party to. Preparing the diff and letting the operator approve it keeps the
authorship where it belongs, and costs one turn.

It is also the only instruction file this skill claims. Naming a runtime's own
files alongside it - `CLAUDE.md`, editor rule files, whatever ships next - buys
nothing, because that runtime already loads them, and it dates the skill the
moment the list changes.

The reporting threshold is narrow because an agent that reports every small
deviation gets tuned out, and a tuned-out reporter is worse than no reporter.
An earlier version drew that line at repetition - the same contradiction a third
time. It could not be held: counting a semantic event across a session needs
state the agent does not have, so the rule fired at random or not at all, and it
failed silently, which is the worst way for a rule to fail. The line is now
falsifiability. Whether the file states something that is no longer true can be
checked at any instant, and a trigger you can check is a trigger that fires.

## Why an absent operator is not an approval

Every approval rule assumes someone is reading. In a scheduled run or a
background agent nobody is, and an agent that reads silence as consent has
quietly converted each approval gate into a rubber stamp - at exactly the moment
no human is watching the result. The opposite failure, stalling on a question
nobody will read, wastes the run and nothing else. Prepare the change, state the
decision it needs, stop.

## Why documentation goes in the same commit

A separate "update the docs" reminder is a task that competes with everything
else on the operator's list and usually loses. The commit that changed the
behaviour is the one that invalidated the document, so that commit is where the
fix is cheapest and most obviously correct.

## Why re-reads are bounded but not gated

Re-reading a file that is already in context usually costs tokens and produces
nothing, so the rule pushes back on it. It does not ask permission for it. An
earlier version of this skill did, which put a free, reversible operation behind
the same gate as writing to disk and contradicted the priority rule one section
above it.

The opposite failure is the expensive one. An agent working from a copy that has
gone stale - its own partial read, an edit it made several turns ago, a file the
operator changed meanwhile - produces a diff against a file that no longer
exists. That is paid for in a wrong patch, not in tokens. So the rule names the
conditions under which the copy you hold stops being trustworthy, and asks for a
one-line reason rather than a turn spent on approval.

The 40 KB threshold is a rough proxy for 10k tokens, and a default rather than a
law - `AGENTS.md` can name another figure, because the right number depends on
the runtime's context budget and on how large the repo's files actually are. The
point is to make the operator's spend visible before it happens, not to defend a
specific number.

## Why creating a file follows the same test as changing one

An earlier version gated every new file while letting some edits through on a
three-condition test. That is backwards. An unwanted new file is deleted in one
command; an edit to a file other work depends on has to be reverted and then
reasoned about again. What matters is whether the write sits inside approved
work and can be undone in one command, not whether it creates a new file.

The exception is a file nobody asked for - a module, a config, a document the
agent decided the repo needed. There the cost of deleting it is beside the
point: the question is whether it should exist at all, and that is the
operator's to answer.

## Why intent narration is banned

"Let me take a look at that file" costs a sentence and tells the operator nothing
they will not learn one line later when the tool call appears. It also reads as
hedging. An approval question is different: it is an actual decision point, and
the operator cannot answer a question you did not ask.

## Why evidence labels matter more than confidence

"It imports and the CLI starts" and "it ran against the real system" describe
very different amounts of risk. An agent that merges them into "it works" is not
being confident, it is transferring an unmeasured risk onto the operator without
telling them. The label is the honest unit of delivery.

## Why the operator runs git

Two reasons. First, `git add`/`commit`/`push` are the last point where a human
can look at what is about to become permanent or public, and a diff scan by the
author of the diff is not a review. Second, path-scoped adds force the agent to
state exactly which files it believes it touched - an assertion that is easy to
check and often wrong.

`git add .` defeats both. It is banned specifically, not as a style preference.

## Why no assistant signature

Trailers like `Co-Authored-By` and "Generated with" put tooling metadata into a
permanent, public record that exists to describe changes to the software. They
also leak how the work was done into repos whose owners may not have chosen to
disclose that. So the default is silence. It is a default and not a rule: a
project that asks for attribution - in its CONTRIBUTING file, its pull request
template or its `AGENTS.md` - has made that choice for itself, and the skill
follows it.
