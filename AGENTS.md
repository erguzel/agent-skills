# AGENTS.md

This repository publishes Agent Skills, one folder per skill under `skills/`.

## Conventions

- A skill's `SKILL.md` is loaded in full every time the skill fires. Keep it
  short; put explanation in that skill's `references/`.
- A rule earns its place by changing what the agent does at a decision point.
- The frontmatter `name` must match the skill's directory name exactly.
- `SKILL.md` stays under 500 lines and its relative links must resolve; the
  validator enforces both.
- The root `README.md` is the index. A new skill gets a row in its table.

## Commands

- Validate: `python tools/validate_skills.py`
- Check the scenario file's structure: `python tools/validate_scenarios.py`
- Test the scenario validator: `python tools/test_validate_scenarios.py`
- Test attribution patterns: `python tools/test_attribution.py`
- Enable commit hooks (once per clone):
  `git config core.hooksPath skills/vier-augen/hooks`

## Behaviour scenarios

- A change to what a rule in a skill's `SKILL.md` says needs the scenarios that
  cover it, run by hand in an agent.
- A new rule is Core or Comfort before it is written, and comes with a scenario
  marked as such. `tests/vier-augen/scenarios.md` defines the two sets.
- A release needs the Core set, plus any Comfort scenario covering what the
  release touches.
- Typo and formatting fixes that change no rule need none.
- Run results are not kept in this repository.
