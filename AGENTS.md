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
- Record a decision under `docs/adr/` when it shapes what later work has to
  live with - a file format, a boundary between components, what runs where,
  what is deliberately not built - and someone who did not make it could
  reasonably choose otherwise. Do not record a fix, a rename, a dependency
  bump, or a preference nobody else has to follow. `docs/adr/README.md` gives
  the format.

## What may be published

This repository is public. Everything committed is read by strangers, and a
document written for one session is the usual way something private slips out.

- Every file in the repository is written in English, for a reader who was not
  in the session that produced it. No "as we discussed", no session or ticket
  numbers that resolve nowhere.
- No personal paths (`/Users/...`, `/home/...`), real hostnames, machine names,
  internal URLs, tokens or keys - not even as an example. Use a placeholder and
  say what the reader has to set.
- No transcript: nothing pasted from a session, no agent output quoted as
  evidence, no operator's name or company.
- `/.ai/` is the scratch directory and is ignored in full - checkpoints, run
  logs, copied transcripts. Nothing in it is committed, and nothing that
  matters long-term is left only in it.

## Commands

- Validate: `python tools/validate_skills.py`
- Check the scenario file's structure: `python tools/validate_scenarios.py`
- Test the scenario validator: `python tools/test_validate_scenarios.py`
- Test the scenario runner's selection: `python tests/vier-augen/test_run.py`
- Test the scenario checks and profile: `python tests/vier-augen/test_harness.py`
- Verify the hooks and the guard: `python tests/vier-augen/run.py verify`
- Run behaviour scenarios (needs an agent): `python tests/vier-augen/run.py S7`
- Test attribution patterns: `python tools/test_attribution.py`
- Enable commit hooks (once per clone):
  `git config core.hooksPath skills/vier-augen/hooks`

## Behaviour scenarios

- A change to what a rule in a skill's `SKILL.md` says needs the scenarios that
  cover it: `python tests/vier-augen/run.py --affected <base>` names them from
  the sections the diff touches, and `run.py <ids>` runs them. When it names
  none, none are owed.
- A release needs the whole Core set, plus any Comfort scenario covering what
  the release touches. The subset above is for a single change; a release does
  not get to skip.
- The subset is only as good as the `Covers` lines it reads. A scenario whose
  `Covers` is wrong drops out of the selection silently, so keep it honest when
  you write one.
- A new rule is Core or Comfort before it is written, and comes with a scenario
  marked as such, block included. `tests/vier-augen/scenarios.md` defines the
  two sets.
- Typo and formatting fixes that change no rule need none.
- Run results are not kept in this repository.
