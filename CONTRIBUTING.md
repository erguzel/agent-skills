# Contributing

Issues and pull requests are welcome.

## How changes are judged

A change is judged against the skill's thesis as well as its quality. A
well-made change that moves a skill away from its position will be declined
politely, with a suggestion to fork. Forking is the intended way to adapt a
skill to another workflow, and the license allows it.

For changes to a skill's rules, open an issue first. A rule earns its place by
changing what the agent does at a decision point; a rule that would not alter
any concrete action belongs in the skill's `references/` or nowhere.

## Before a pull request

```bash
python tools/validate_skills.py
python tools/test_attribution.py
```

Commits must not carry assistant attribution - no `Co-Authored-By` trailers for
agents, no "Generated with" lines, no session links. CI checks commit messages,
authors and the pull request description.
