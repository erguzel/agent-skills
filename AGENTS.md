# AGENTS.md

This repository publishes Agent Skills, one folder per skill under `skills/`.
Follow `skills/repo-conduct/SKILL.md` for session conduct, approvals and
commit handover while working here.

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
- Enable commit hooks (once per clone):
  `git config core.hooksPath skills/repo-conduct/hooks`
