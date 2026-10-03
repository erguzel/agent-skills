# Roadmap

What is being worked on, what waits on it, and what is wanted but not yet
shaped. The list is ordered, not dated: nothing here is a schedule or a
promise, and an item moves when what was learned from the one before it says
so. A decision taken along the way is recorded under `adr/`, not here.

## Now

- **A control arm for the baseline.** The Core baseline ran only with the
  skill loaded, so it cannot say how much of the result is the skill and how
  much the model does anyway. The runner gets a mode that runs without the
  skill and labels the result as control, not invalid; the Core set runs once
  that way and is compared with the baseline. If the difference is small, the
  weight of this project sits in the harness and the mechanical layer more
  than in the text.

## Next

- **A smaller model.** The same Core set on a smaller open-weights model, to
  learn whether the text carries when the model is not a frontier one, or
  whether that weight belongs to the hooks, the adapters and the classifier.
  It is tried first through an agent that already has a profile.
- **A judge for `expected` and `fail_if`.** A run settles its `checks` on its
  own, and a `says` check can match a pattern in what the agent said; the
  prose of `expected` and `fail_if` is still read by a person. The judge adds
  the missing step - a model reading the transcript against that prose - and
  a person is asked only for what comes back undetermined. The baseline's
  transcripts are the first body to design it against; it gets a short
  specification before code.
- **A second agent.** An agent is a profile and an adapter; a model is a
  parameter of a run. A second agent is a profile beside the Claude Code one,
  as a package with its own tests, and an adapter under the skill that wraps
  the shared classifier rather than copying it. A model served through an
  agent that already has a profile needs neither.
- **Real use, outside this repository.** The skill has so far governed work on
  itself. Using it on a project that is not its own is what measures its
  friction, and what says whether the read budget, the approval steps and the
  handover of commands are set right.
- **The mechanical layer on Windows and macOS.** `run.py verify` runs in CI on
  Linux only. The hooks are POSIX shell and the guard is Python; neither has
  been tried on Windows.

## Later

- **Attribution patterns for more agents.** Gemini CLI, Windsurf, Cline, Kiro
  and Factory Droid are not covered yet; each needs the form its attribution
  takes, taken from real commits, not guessed.
- **A second skill.** A working agreement for the craft of the code itself,
  separate from vier-augen, which governs the process. It is also what forces
  the choice the architecture leaves open: whether the harness serves many
  skills or each skill brings its own test tree.

## Not planned

- **A ranking of agents.** The scenarios say whether the skill's text holds
  under an agent and a model. Running them across agents or models to say
  which is better is not a goal, and the harness is not built to make that
  comparison fair.
