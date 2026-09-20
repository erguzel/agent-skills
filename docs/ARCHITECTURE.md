# Architecture

This file names the parts of this repository and what each one promises the
others. It says what is true now. It does not say why - `adr/` records the
decisions - and it does not describe how a part works inside, so that it
stays true when the inside changes. `AGENTS.md` says what a contributor does;
a skill's own `README.md` says how to use it.

Two kinds of section follow. "Two products in one tree", "Continuous
integration" and "Deliberately absent" hold for every skill this repository
will ever carry. The sections headed `vier-augen` describe the one skill here
today and the machinery that tests it; a second skill does not extend them,
it brings its own.

## Two products in one tree (every skill)

The tree holds a shipped product and the machinery that tests it.

- `skills/<name>/` is the product. It is installed by copying the folder, and
  everything the skill needs at run time is inside that folder: the text, the
  hooks, the adapters, the CI template, the references.
- `tests/` and `tools/` are never shipped. They read the skill.

Dependencies point one way. The test side may import from the skill; nothing
under `skills/` may depend on `tests/` or `tools/`. A skill has to work in a
tree where they do not exist.

## vier-augen: the layers

The skill protects in four layers, switched on separately, none assuming
another.

| Layer | Where | Promise |
| --- | --- | --- |
| 0 - text | `SKILL.md`, `references/` | Steers the agent while it is invoked. Loaded in full, so it stays short; explanation lives in `references/`. |
| 1 - git hooks | `hooks/` | `commit-msg` refuses assistant attribution and agent identities; `pre-commit` refuses staged secrets and personal paths; `pre-push` refuses a rewrite of remote history. POSIX `sh`, and they never overwrite a hook that is already there. |
| 2 - agent adapter | `adapters/<agent>/` | Makes the agent runtime ask before an Operator-tier command runs and refuse a force-push. One adapter per agent. |
| 3 - CI template | `ci/` | Fails a pull request that carries attribution, in a repository where the hook was not installed. |

Layer 0 and the mechanical layers cover overlapping rules by different means,
which is why they are measured apart (ADR 0002): a hook that is on hides
whether the text worked.

The attribution patterns under `hooks/attribution/` are the single source for
every layer that matches attribution. The `commit-msg` hook reads the files;
the CI template embeds a copy, and a test in `tools/` keeps the copy identical
to the files.

An adapter's decisions and the messages the hooks print are an interface: the
runner's `verify` matches them, so a deliberate change to either changes its
check in the same commit.

An agent is supported by the adapter when it has one under `adapters/`, and
measured by the behaviour scenarios when it has a profile of the same name
under `tests/vier-augen/profiles/`. Until an agent has both, layers 0, 1 and 3
apply to it.

## vier-augen: how it is tested

### One entry point

`tests/vier-augen/run.py` is the only way in (ADR 0002).

- `run.py verify` measures the mechanical layers: it builds a throwaway
  repository, installs the hooks there and hands each hook and the guard the
  input it is meant to stop. Hooks on, no agent, deterministic, free. CI runs
  it on every change.
- `run.py <scenarios>` measures the text: it drives a live agent through the
  scenarios against a fixture with the hooks off. It costs tokens, and CI
  never runs it.

The two are refused in one command.

The runner, the harness and the scenario validator read one skill, by name.
A second skill with behaviour scenarios of its own would force a choice that
has not been made: generalise the harness and give each skill a scenario file,
or give each skill a test tree. Nothing here anticipates either.

### The scenario file

`tests/vier-augen/scenarios.md` is the single source for the behaviour
scenarios (ADR 0001). A scenario is prose followed by one JSON block. The
runner reads three things from the prose - the identifier, the `Set` and the
`Covers` line - and everything else from the block: `setup`, `steps`,
`expected`, `fail_if`, `checks`, and the optional `continues`, `fixture` and
`mode`.

`Covers` names sections of `SKILL.md` by their headings. That mapping is what
`run.py --affected <base>` reads to name the scenarios a change owes (ADR
0005), so a `Covers` line is part of the contract, not a comment.

`tools/validate_scenarios.py` holds the check vocabulary and enforces the
shape of the file; `harness.py` realises every name in that vocabulary. A name
known to one and not the other is a defect. The checks fall into three groups:
what the agent attempted, read from the transcript; the files, compared with
the baseline; and the commits and the remote.

### The harness and the profiles

`tests/vier-augen/harness.py` is agent-neutral (ADR 0003). It owns the
transcript model - a flat list of events that are a user message, agent text
or a tool call - the classification of a shell command, the realisation of
every check, and two rules that make a result trustworthy:

- a check that cannot be settled returns undetermined, and undetermined is
  never a pass;
- a session the skill's text never reached is invalid as a whole, and says
  nothing about the skill.

Everything specific to one agent lives in a profile under `profiles/`. A
profile provides: how the operator invokes the skill; where the agent looks
for skills; which tool names write, which only read, and which are safe; how
to launch one headless turn and how to resume the session for the next; a
preflight that refuses to measure a session an adapter or a personal
instruction file would mask; and how to find a transcript and turn it into
the harness's event list. The harness names no tool and no path of any
agent; the directories an agent owns in the fixture, which the file checks
leave out, are read from the profile too.

The harness classifies a command with the skill's own module, `lib/tiers.py`,
the same one every adapter's guard reads, so the test and the guard cannot
disagree on what a command does (ADR 0007; ADR 0003 had recorded the earlier
import from one adapter as a known exception).

### Sessions, chains and judgment

A scenario can continue another. The chain shares one agent conversation and
one fixture, and nothing else: each scenario is judged on its own span of the
conversation (ADR 0006). The driver judges a scenario the moment its last step
is answered, before the next scenario's first message. The manual driver
judges a finished session, bounding each scenario's transcript by the next
scenario's first message; it sees the files only as the whole session left
them, so a state check inside a chain is weaker there.

A scenario result is one of pass, fail, undetermined or invalid.

### The fixture

`build-fixture.sh` builds a throwaway repository outside this tree, with a
bare remote beside it and the hooks off, and links the skill in where the
agent under test looks for it. The fixture deliberately carries instructions
aimed at agents - a file demanding answers in another language, a line asking
for a directory to be deleted - because not following them is what the
scenarios measure. A scenario's `setup` runs in the fixture before the session,
and the baseline the file checks compare against is taken after `setup`.

Both locations are settable: `VA_FIXTURE` for the fixture, `VA_RESULTS` for
the results. The builder refuses a fixture inside this repository; results
stay outside it by the rule in ADR 0004, which nothing enforces.

### Results

Results are written outside the repository and never committed (ADR 0004).
`run.py --report` reads the latest per scenario from there. Evidence of a run
goes into the pull request that relies on it, with the agent, the model
version and the operating system.

### Not built

- A harness per agent. One harness, a profile per agent (ADR 0003).
- A ranking of agents. The scenarios say whether the text holds under an
  agent; they are not built to say which agent is better.

## Continuous integration (every skill)

`.github/workflows/validate.yml` runs everything that needs no agent: the
skill validator, the scenario validator and its tests, the runner's selection
and check tests, the attribution tests, and `run.py verify`. On a pull request
it also refuses assistant attribution in the commits and the description,
reading the pattern files directly.

What CI does not run is the behaviour scenarios. They need an agent, so they
run on a contributor's machine, and their outcome is reported in the pull
request.

The test side needs Python's standard library and git, nothing else. The hooks
and the fixture builder are POSIX `sh`.

## Deliberately absent (every skill)

- Run results in the tree (ADR 0004).
- Third-party dependencies on the test side.
