# skills

A collection of [Agent Skills](https://agentskills.io) — portable instruction
folders that any Skills-compatible AI agent can load.

One folder per skill under `skills/`. Each is self-contained, so you can install
one without taking the rest.

## Skills

| Skill | What it does |
| --- | --- |
| [`vier-augen`](skills/vier-augen/) | A four-eyes working agreement for agentic development in a git repository: the agent works fast, the operator owns every permanent, destructive or publishing step, and the agent hands those over as commands. Invoked by name only. |

## Install

The [`skills` CLI](https://github.com/vercel-labs/skills) installs one skill by
name:

```bash
npx skills add erguzel/skills --skill vier-augen
```

`--skill '*'` takes all of them. Or copy the folder into wherever your agent
looks for skills. Directory conventions differ between agents and change fairly
often — check your agent's own documentation, or let the CLI place it for you.

## Layout

```
skills/
└── <skill-name>/
    ├── SKILL.md            # required: frontmatter + instructions
    ├── README.md           # optional: the human-facing page for this skill
    ├── hooks/              # optional: git hooks the skill ships, opt-in
    └── references/         # optional: read on demand, not loaded up front
tools/
└── validate_skills.py      # spec checks, run over every skill in CI
.github/workflows/
└── validate.yml            # runs the validator on every push and pull request
AGENTS.md                   # how agents should behave inside THIS repo
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
budget, and that every relative link in `SKILL.md` resolves. CI runs it on every
push and pull request.

## Contributing

Issues and PRs welcome. Run the validator before opening one.

## License

Apache-2.0. See [LICENSE](LICENSE).
