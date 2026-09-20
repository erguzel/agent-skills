# agent-skills

A collection of [Agent Skills](https://agentskills.io) — portable instruction
folders that any Skills-compatible AI agent can load.

One folder per skill under `skills/`. Each is self-contained, so you can install
one without taking the rest.

These skills are written for the way I work. They are public so anyone can use
them, but they don't try to fit everyone.

## Skills

| Skill | What it does |
| --- | --- |
| [`vier-augen`](skills/vier-augen/) | A four-eyes working agreement for agentic development in a git repository: the agent works fast, the operator owns every permanent, destructive or publishing step, and the agent hands those over as commands. Invoked by name only. |

## Install

The [`skills` CLI](https://github.com/vercel-labs/skills) installs one skill by
name:

```bash
npx skills add erguzel/agent-skills --skill vier-augen
```

`--skill '*'` takes all of them. Or copy the folder into wherever your agent
looks for skills. Directory conventions differ between agents and change fairly
often — check your agent's own documentation, or let the CLI place it for you.

Installing places files and nothing else. A skill that ships git hooks, agent
adapters or CI templates documents how to switch them on in its own README -
for `vier-augen`, see [Setup](skills/vier-augen/README.md#setup).

## Layout

```
skills/
└── <skill-name>/
    ├── SKILL.md            # required: frontmatter + instructions
    ├── README.md           # optional: the human-facing page for this skill
    ├── hooks/              # optional: git hooks the skill ships, opt-in
    ├── adapters/           # optional: per-agent settings templates, opt-in
    ├── ci/                 # optional: CI templates for your own repos, opt-in
    └── references/         # optional: read on demand, not loaded up front
tools/
├── validate_skills.py          # spec checks, run over every skill in CI
├── validate_scenarios.py       # structure checks for the scenario file, in CI
├── test_validate_scenarios.py  # tests for that validator, in CI
└── test_attribution.py         # tests for the vier-augen attribution patterns
tests/
└── vier-augen/
    ├── scenarios.md        # the behaviour scenarios themselves
    ├── build-fixture.sh    # the throwaway repository they run against
    ├── run.py              # one entry point: verify, and the scenarios
    ├── harness.py          # agent-neutral: the checks, over transcript and files
    ├── profiles/           # per-agent: how to drive it and read its transcript
    ├── test_run.py         # tests for selection and the driver, in CI
    └── test_harness.py     # tests for the checks and the profile, in CI
docs/
├── ARCHITECTURE.md         # the parts, and what each promises the others
├── ROADMAP.md              # what is being worked on, and what waits on it
└── adr/                    # decisions about how this repository is built and tested
.github/workflows/
└── validate.yml            # runs the validator on every push and pull request
AGENTS.md                   # how agents should behave inside THIS repo
CONTRIBUTING.md             # how changes are judged
LICENSE                     # Apache-2.0, covers every skill in this repo
```

`SKILL.md` is loaded in full whenever the skill fires, so it is kept short.
Anything that only matters sometimes goes under `references/`.

## Adding a skill

1. Create `skills/<skill-name>/SKILL.md`. The frontmatter `name` must be
   lowercase, hyphen-separated and identical to the directory name.
2. Write the `description` for triggering: what the skill does *and* when an
   agent should reach for it. It is the only field an agent sees before deciding
   whether to load the skill.
3. Keep `SKILL.md` short. A rule earns its place by changing what the agent does
   at a decision point; the reasoning behind it belongs in `references/`.
4. Add a row to the table above.
5. Run `python tools/validate_skills.py`.

## Validate

```bash
python tools/validate_skills.py
```

Checks every skill folder under `skills/`: that it holds a `SKILL.md`, that the
frontmatter parses and carries the required fields, that `name` matches the
directory and the field limits hold, that the body stays inside the 500-line
budget, that every relative link in `SKILL.md` resolves, that every shipped
script with a shebang is executable, and that every shipped JSON file parses. CI
runs it on every push and pull request.

```bash
python tools/validate_scenarios.py
```

Checks the shape of `tests/vier-augen/scenarios.md`: that every scenario
carries a `Set` marker of `Core` or `Comfort`, that the numbering runs from 1
without gaps, that the Core scenarios come before the Comfort ones, and that a
scenario referring to another names one that exists and comes earlier, and
that each scenario's JSON block is well-formed and names only known checks. It
says nothing about whether a scenario is any good. CI runs it too.

```bash
python tools/test_attribution.py
```

Runs the `vier-augen` attribution patterns against messages and identities that
must be blocked or let through, and checks that the copy embedded in the CI
template matches the pattern files. CI runs it too.

## Behaviour scenarios

```
tests/vier-augen/scenarios.md
```

Twenty-one situations, each marked Core or Comfort, that check whether a
skill's text changes what an agent does: each gives the messages to send, what
to expect, what counts as a failure, and the checks that need no judgment.

```bash
python3 tests/vier-augen/run.py --list      # what there is
python3 tests/vier-augen/run.py S7          # run one, and the session it continues
```

The runner builds a throwaway fixture, drives an agent through the steps and
judges the checks against the transcript and the fixture. It needs an agent, so
it costs tokens and CI does not run it - CI checks the file's structure, the
runner's own selection, and the checks themselves. A check it cannot settle
comes back undetermined rather than passing. Results are written outside this
repository and are not kept here.

## Contributing

Issues and pull requests are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md)
for how changes are judged.

## License

Apache-2.0. See [LICENSE](LICENSE).
